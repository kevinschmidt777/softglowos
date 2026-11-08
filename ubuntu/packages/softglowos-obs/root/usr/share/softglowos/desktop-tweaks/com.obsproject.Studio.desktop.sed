# OBS starts through softglowos-obs, which prepares encoder and mixer audio on
# the very first start (files/scripts/preconfigure-obs.sh on Fedora), and on
# the strong GPU of laptops with two (prefer-dedicated-gpu.sh)
s|^Exec=obs$|Exec=softglowos-obs|
s|^Exec=obs |Exec=softglowos-obs |
/^\[Desktop Entry\]$/a PrefersNonDefaultGPU=true
/^PrefersNonDefaultGPU=/d
