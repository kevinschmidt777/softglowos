# Ubuntu's entry is called "Install Steam" until Steam puts its own one into
# the home folder on the first start; ours is just Steam, on the strong GPU
# of laptops with two (Game Capture comes from /usr/games/steam)
s/^Name=.*/Name=Steam/
/^Name\[/d
/^\[Desktop Entry\]$/a PrefersNonDefaultGPU=true
/^PrefersNonDefaultGPU=/d
