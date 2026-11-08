# OBS starts through softglowos-obs, which prepares encoder and mixer audio on
# the very first start, and on the strong GPU of laptops with two
s|^Exec=obs$|Exec=softglowos-obs|
s|^Exec=obs |Exec=softglowos-obs |
/^\[Desktop Entry\]$/a PrefersNonDefaultGPU=true
/^PrefersNonDefaultGPU=/d
