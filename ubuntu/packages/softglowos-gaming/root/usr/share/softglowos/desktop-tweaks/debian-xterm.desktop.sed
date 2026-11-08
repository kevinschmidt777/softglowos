# Valve's Steam launcher pulls in XTerm (for its own dependency check);
# Ptyxis is our terminal, so XTerm stays out of the app grid
/^NoDisplay=/d
/^\[Desktop Entry\]$/a NoDisplay=true
