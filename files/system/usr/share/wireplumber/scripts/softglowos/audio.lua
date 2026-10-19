-- SoftglowOS audio routing (see tools/make-audio-config.py for the graph).
--
-- 1. App streams go into a mixer channel (chat, music, browser, game,
--    everything else system). A channel the user picked in the Hub wins:
--    WirePlumber's own find-defined-target hook runs first and restores it.
-- 2. Our own loopbacks get their targets from here, depending on whether a
--    GoXLR is connected (it then mixes in hardware) or not. A loopback that
--    has nothing to do in the current mode stays unlinked.
-- 3. The microphone chain records the best real microphone (or the GoXLR's
--    "Chat Mic"), the console channel the capture card. Neither falls back
--    to anything else, and a device picked in the Hub wins.
-- 4. Filter settings (EQ, gate, ...) and the offsets are remembered.

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

-- GoXLR channels by their ALSA UCM names (alsa-ucm-conf, USB-Audio/GoXLR).
local GOXLR_SINKS = { game = "Game", chat = "Chat", music = "Music", system = "System" }
local GOXLR_SAMPLE = "Sample"        -- browser and console go here
local GOXLR_STREAM_MIX = "Stream Mix 1"
local GOXLR_CHAT_MIC = "Chat Mic"

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

local function is_goxlr (props)
  for _, key in ipairs { "alsa.card_name", "api.alsa.card.name", "device.product.name", "node.description" } do
    if matches_any (props [key], { "goxlr" }) then
      return true
    end
  end
  return false
end

local function is_capture_card (props)
  return not is_goxlr (props) and (
      matches_any (props ["node.description"], CAPTURE_CARDS) or
      matches_any (props ["device.product.name"], CAPTURE_CARDS) or
      matches_any (props ["node.nick"], CAPTURE_CARDS))
end

local function find_by_name (om, name)
  return om:lookup {
    type = "SiLinkable",
    Constraint { "node.name", "=", name },
  }
end

-- A GoXLR sink or source by its UCM name ("Game", "Chat Mic", ...).
local function goxlr_node (om, media_class, ucm_name)
  for target in om:iterate {
    type = "SiLinkable",
    Constraint { "media.class", "=", media_class },
  } do
    local props = target.properties
    if is_goxlr (props) then
      local profile = props ["device.profile.description"]
      local description = props ["node.description"] or ""
      if profile == ucm_name or description:sub (- #ucm_name - 1) == " " .. ucm_name then
        return target
      end
    end
  end
  return nil
end

local function goxlr_connected (om)
  return goxlr_node (om, "Audio/Sink", GOXLR_SINKS.system) ~= nil
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

-- RNNoise state of the mic chain and whether the mic has an offset, kept up
-- to date by the filter code below.
local rnnoise_on = true
local mic_offset_on = false
local MIC_OFFSET = PREFIX .. "mic.mix.in"

-- Where one of our own loopbacks belongs right now. Returns the target (or
-- nil to stay unlinked), or "keep" to leave WirePlumber's choice alone.
local function own_target (om, si_props, si_flags)
  local name = si_props ["node.name"]
  local goxlr = goxlr_connected (om)

  if name == PREFIX .. "mic.in" then
    if si_flags.has_defined_target then
      return "keep"
    end
    if goxlr then
      return goxlr_node (om, "Audio/Source", GOXLR_CHAT_MIC)
    end
    return best_device (om, si_props, "Audio/Source", function (props)
      return not is_capture_card (props) and not is_goxlr (props)
    end)
  elseif name == PREFIX .. "console-offset.in" then
    if si_flags.has_defined_target then
      return "keep"
    end
    return best_device (om, si_props, "Audio/Source", is_capture_card)
  elseif name == PREFIX .. "goxlr-stream.in" then
    return goxlr and goxlr_node (om, "Audio/Source", GOXLR_STREAM_MIX) or nil
  elseif name == PREFIX .. "mic.mix.out" then
    -- With a GoXLR the mic is already in its hardware stream mix, unless
    -- RNNoise or an offset is on: then the Hub takes it out there and we add
    -- it here.
    if goxlr and not rnnoise_on and not mic_offset_on then
      return nil
    end
    return find_by_name (om, PREFIX .. "stream-mix")
  end

  local channel, role = name:match ("^softglowos%.([%w]+)%.([%w]+)%.out$")
  if channel == nil then
    return "keep"
  end
  local hardware = goxlr and GOXLR_SINKS [channel]

  if role == "mix" then
    return (not hardware) and find_by_name (om, PREFIX .. "stream-mix") or nil
  elseif role == "monitor" then
    if hardware then
      return nil
    elseif goxlr then
      return goxlr_node (om, "Audio/Sink", GOXLR_SAMPLE)
    end
    return default_output (om, si_props)
  elseif role == "goxlr" then
    return hardware and goxlr_node (om, "Audio/Sink", hardware) or nil
  end
  return "keep"
end

-- App streams: pick a channel unless the user already picked one.
SimpleEventHook {
  name = "linking/softglowos-find-app-target",
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
    if target or is_ours (si_props ["node.name"]) or
        si_props ["media.class"] ~= "Stream/Output/Audio" or
        app_matches (si_props, UNTOUCHED_APPS) then
      return
    end
    local channel = channel_for (si_props)
    local picked = find_by_name (om, PREFIX .. channel)
    if picked then
      log:info (si, string.format ("%s -> %s", tostring (si_props ["application.name"]), channel))
      event:set_data ("target", picked)
    end
  end
}:register ()

-- Our own loopbacks: runs after all other finders and has the last word.
SimpleEventHook {
  name = "linking/softglowos-own-targets",
  after = {
    "linking/find-defined-target",
    "linking/find-audio-group-target",
    "linking/find-filter-target",
    "linking/find-media-role-target",
    "linking/find-default-target",
    "linking/find-best-target",
    "linking/find-media-role-sink-target",
    "linking/get-filter-from-target",
    "linking/softglowos-find-app-target",
  },
  before = "linking/prepare-link",
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-target" },
    },
  },
  execute = function (event)
    local source, om, si, si_props, si_flags, target =
        lutils:unwrap_select_target_event (event)
    if not is_ours (si_props ["node.name"]) then
      return
    end
    local wanted = own_target (om, si_props, si_flags)
    if wanted ~= "keep" then
      log:debug (si, string.format ("%s -> %s", si_props ["node.name"],
          wanted and tostring (wanted.properties ["node.name"]) or "(unlinked)"))
      event:set_data ("target", wanted)
    end
  end
}:register ()

local function rescan ()
  local source = Plugin.find ("standard-event-source")
  if source then
    source:call ("schedule-rescan", "linking")
  end
end

-- Remember filter settings (EQ, gate, compressor, RNNoise) and offsets.

local state = State ("softglowos-audio")
local saved = state:load ()

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
  if not found then
    return
  end
  saved [node.properties ["node.name"]] = Json.Object (values):to_string ()
  state:save_after_timeout (saved)

  local gain = values ["rnnoise_mix:Gain 1"]
  if gain ~= nil and (gain > 0.5) ~= rnnoise_on then
    rnnoise_on = gain > 0.5
    rescan ()
  end
  if node.properties ["node.name"] == MIC_OFFSET then
    local on = (values ["offset:Delay (s)"] or 0) > 0
    if on ~= mic_offset_on then
      mic_offset_on = on
      rescan ()
    end
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
  if values ["rnnoise_mix:Gain 1"] ~= nil then
    rnnoise_on = values ["rnnoise_mix:Gain 1"] > 0.5
  end
  if node.properties ["node.name"] == MIC_OFFSET then
    mic_offset_on = (values ["offset:Delay (s)"] or 0) > 0
  end
  if #params > 0 then
    node:set_param ("Props", Pod.Object {
      "Spa:Pod:Object:Param:Props", "Props",
      params = Pod.Struct (params),
    })
  end
end

-- The mic chain and every delay filter behind an offset.
local FILTER_NODES = { PREFIX .. "mic.in", PREFIX .. "console-offset.in", MIC_OFFSET }
for _, channel in ipairs ({ "game", "chat", "music", "system", "browser" }) do
  for _, path in ipairs ({ "stream", "monitor", "goxlr" }) do
    if path ~= "goxlr" or GOXLR_SINKS [channel] then
      table.insert (FILTER_NODES, PREFIX .. channel .. "." .. path .. ".in")
    end
  end
end

filters_om = ObjectManager {
  Interest {
    type = "node",
    Constraint { "node.name", "c", table.unpack (FILTER_NODES) },
  }
}

filters_om:connect ("object-added", function (_, node)
  restore_params (node)
  node:connect ("params-changed", function (n, id)
    if id == "Props" then
      save_params (n)
    end
  end)
end)

filters_om:activate ()
