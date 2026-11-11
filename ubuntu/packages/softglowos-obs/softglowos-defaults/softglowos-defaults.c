/*
 * SoftglowOS defaults for OBS: settings OBS ships one way and SoftglowOS
 * wants the other way, set once per source as it shows up.
 *
 * Video capture devices (capture cards, webcams): "Use buffering" off. With
 * buffering on, OBS queues their frames, and when the graphics card hangs for
 * a moment (e.g. a monitor switched to another input) the queue grows and
 * stays: picture and sound of the console or camera are out of sync for the
 * rest of the stream. Without buffering OBS shows the newest frame, measured
 * at +-30 ms before and after a switch, against up to 800 ms with it.
 *
 * Each source gets a marker after the first time, so a user who turns
 * buffering back on keeps it.
 */
#include <obs-module.h>
#include <string.h>

OBS_DECLARE_MODULE()

#define MARKER "softglowos-defaults"

MODULE_EXPORT const char *obs_module_description(void)
{
	return "SoftglowOS defaults: video capture devices without buffering";
}

static void source_created(void *data, calldata_t *cd)
{
	(void)data;
	obs_source_t *source = calldata_ptr(cd, "source");
	if (!source)
		return;
	const char *id = obs_source_get_unversioned_id(source);
	if (!id || strcmp(id, "v4l2_input") != 0)
		return;

	obs_data_t *settings = obs_source_get_settings(source);
	bool done = obs_data_has_user_value(settings, MARKER);
	obs_data_release(settings);
	if (done)
		return;

	obs_data_t *change = obs_data_create();
	obs_data_set_bool(change, "buffering", false);
	obs_data_set_bool(change, MARKER, true);
	obs_source_update(source, change);
	obs_data_release(change);
	blog(LOG_INFO, "[softglowos-defaults] '%s': buffering off", obs_source_get_name(source));
}

bool obs_module_load(void)
{
	signal_handler_connect(obs_get_signal_handler(), "source_create", source_created, NULL);
	return true;
}

void obs_module_unload(void)
{
	signal_handler_disconnect(obs_get_signal_handler(), "source_create", source_created, NULL);
}
