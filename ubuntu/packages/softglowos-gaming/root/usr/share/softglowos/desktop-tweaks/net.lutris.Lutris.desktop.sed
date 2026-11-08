# Games start with OBS_VKCAPTURE=1 for OBS's Game Capture (launch option
# OBS_VKCAPTURE=0 opts a game out), on the strong GPU of laptops with two
/^Exec=env OBS_VKCAPTURE=1 /! s/^Exec=/Exec=env OBS_VKCAPTURE=1 /
/^\[Desktop Entry\]$/a PrefersNonDefaultGPU=true
/^PrefersNonDefaultGPU=/d
