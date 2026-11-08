# GNOME Software only opens downloaded .deb files; apps come from the
# Softglow Store
/^\[Desktop Entry\]$/a NoDisplay=true
/^NoDisplay=/d
