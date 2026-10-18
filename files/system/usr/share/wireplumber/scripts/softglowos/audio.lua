-- SoftglowOS audio routing (see tools/make-audio-config.py for the graph).
--
-- 1. App streams go into a mixer channel (chat, music, browser, game,
--    everything else system). A channel the user picked in the Hub wins:
--    WirePlumber's own find-defined-target hook runs first and restores it.
-- 2. The headphone side of every channel goes to the default output, but
--    never into one of our own sinks (that would loop).
-- 3. The microphone chain records the best real microphone, the console
--    channel records the capture card. Neither ever falls back to anything
--    else.
-- 4. Filter settings (EQ, gate, ...) and the console offset are remembered.

lutils = require ("linking-utils")
cutils = require ("common-utils")
log = Log.open_topic ("s-softglowos")

local PREFIX = "softglowos."

-- Checked in this order against the app's binary and name (lowercase).
local CHANNEL_RULES = {
  { channel = "chat", match = { "discord", "vesktop", "webcord", "teamspeak", "ts3client", "mumble" } },
  { channel = "music", match = { "spotify", "cider", "tidal", "rhythmbox", "lollypop", "amberol", "elisa" } },
  { channel = "browser", match = { "chrome", "chromium", "firefox", "brave", "librewolf", "vivaldi", "opera", "msedge", "epiphany" } },
  { channel = "game", match = { "wine", "proton", ".exe", "steam_app" } },
}

-- Apps whose sound must never go into the mixer (OBS monitoring would feed
-- the stream back into itself).
local UNTOUCHED_APPS = { "obs" }

-- Capture cards, matched against the device name (lowercase).
local CAPTURE_CARDS = { "elgato", "game capture", "cam link", "avermedia", "live gamer", "usb3.0 capture", "hdmi capture" }

local function is_ours (name)
  return name ~= nil and name:sub (1, #PREFIX) == PREFIX
end

local function matches_any (text, words)
  if text == nil then
    return false
  end
  text = text:lower ()
  for _, word in ipairs (words) do
    if text:find (word, 1, true) then
      return true
    end
  end
  return false
end

local function app_matches (props, words)
  return matches_any (props ["application.process.binary"], words) or
      matches_any (props ["application.name"], words)
end

local function channel_for (props)
  for _, rule in ipairs (CHANNEL_RULES) do
    if app_matches (props, rule.match) then
      return rule.channel
    end
  end
  return "system"
end

local function is_capture_card (props)
  return matches_any (props ["node.description"], CAPTURE_CARDS) or
      matches_any (props ["device.product.name"], CAPTURE_CARDS) or
      matches_any (props ["node.nick"], CAPTURE_CARDS)
end

local function find_by_name (om, name)
  return om:lookup {
    type = "SiLinkable",
    Constraint { "node.name", "=", name },
  }
end

-- The real device with the highest priority that passes the filter.
local function best_device (om, si_props, media_class, accept)
  local best, best_priority = nil, -1
  for target in om:iterate {
    type = "SiLinkable",
    Constraint { "media.class", "=", media_class },
  } do
    local props = target.properties
    local priority = tonumber (props ["priority.session"]) or 0
    if not is_ours (props ["node.name"]) and accept (props) and
        lutils.canLink (si_props, target) and priority > best_priority then
      best, best_priority = target, priority
    end
  end
  return best
end

local function default_output (om, si_props)
  local default_id = cutils.getDefaultNode (si_props, "input")
  if default_id and default_id ~= Id.INVALID then
    local target = om:lookup {
      type = "SiLinkable",
      Constraint { "node.id", "=", tostring (default_id) },
    }
    if target and not is_ours (target.properties ["node.name"]) and
        lutils.canLink (si_props, target) then
      return target
    end
  end
  return best_device (om, si_props, "Audio/Sink", function () return true end)
end

SimpleEventHook {
  name = "linking/softglowos-find-target",
  after = "linking/find-defined-target",
  before = {
    "linking/find-audio-group-target",
    "linking/find-filter-target",
    "linking/find-media-role-target",
    "linking/find-default-target",
    "linking/find-best-target",
  },
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-target" },
    },
  },
  execute = function (event)
    local source, om, si, si_props, si_flags, target =
        lutils:unwrap_select_target_event (event)
    if target then
      return
    end

    local name = si_props ["node.name"]
    local media_class = si_props ["media.class"]
    local picked = nil

    if name == PREFIX .. "mic.in" then
      picked = best_device (om, si_props, "Audio/Source", function (props)
        return not is_capture_card (props)
      end)
    elseif name == PREFIX .. "console-offset.in" then
      picked = best_device (om, si_props, "Audio/Source", is_capture_card)
    elseif is_ours (name) and name:match ("%.monitor%.out$") then
      picked = default_output (om, si_props)
    elseif is_ours (name) then
      return
    elseif media_class == "Stream/Output/Audio" and not app_matches (si_props, UNTOUCHED_APPS) then
      local channel = channel_for (si_props)
      picked = find_by_name (om, PREFIX .. channel)
      log:info (si, string.format ("%s -> %s",
          tostring (si_props ["application.name"]), channel))
    else
      return
    end

    if picked then
      event:set_data ("target", picked)
    elseif is_ours (name) then
      -- No suitable device right now: stay unlinked instead of falling back
      -- to something else. A rescan runs when devices come and go.
      event:stop_processing ()
    end
  end
}:register ()

-- Remember filter settings (EQ, gate, compressor, RNNoise, console offset).

local state = State ("softglowos-audio")
local saved = state:load ()

local FILTER_NODES = {
  [PREFIX .. "mic.in"] = true,
  [PREFIX .. "console-offset.in"] = true,
}

-- Only the controls the Hub offers. The node's Props also hold PipeWire's own
-- settings and values the filters compute themselves, which we leave alone.
local SAVED_CONTROLS = {
  "^rnnoise_mix:Gain [12]$",
  "^gate:Bypass$",
  "^compressor:Bypass$",
  "^eq%d+:Gain$",
  "^offset:Delay %(s%)$",
}

local function is_filter_control (key, value)
  if type (key) ~= "string" or
      (type (value) ~= "number" and type (value) ~= "boolean") then
    return false
  end
  for _, pattern in ipairs (SAVED_CONTROLS) do
    if key:match (pattern) then
      return true
    end
  end
  return false
end

local function save_params (node)
  local values = {}
  local found = false
  for pod in node:iterate_params ("Props") do
    local props = cutils.parseParam (pod, "Props")
    local params = props and props.params
    if params then
      for i = 1, #params, 2 do
        if is_filter_control (params [i], params [i + 1]) then
          values [params [i]] = params [i + 1]
          found = true
        end
      end
    end
  end
  if found then
    saved [node.properties ["node.name"]] = Json.Object (values):to_string ()
    state:save_after_timeout (saved)
  end
end

local function restore_params (node)
  local stored = saved [node.properties ["node.name"]]
  if not stored then
    return
  end
  local values = Json.Raw (stored):parse ()
  local params = {}
  for key, value in pairs (values) do
    if is_filter_control (key, value) then
      table.insert (params, key)
      table.insert (params, value)
    end
  end
  if #params > 0 then
    node:set_param ("Props", Pod.Object {
      "Spa:Pod:Object:Param:Props", "Props",
      params = Pod.Struct (params),
    })
  end
end

filters_om = ObjectManager {
  Interest {
    type = "node",
    Constraint { "node.name", "c", PREFIX .. "mic.in", PREFIX .. "console-offset.in" },
  }
}

filters_om:connect ("object-added", function (_, node)
  if not FILTER_NODES [node.properties ["node.name"]] then
    return
  end
  restore_params (node)
  node:connect ("params-changed", function (n, id)
    if id == "Props" then
      save_params (n)
    end
  end)
end)

filters_om:activate ()
