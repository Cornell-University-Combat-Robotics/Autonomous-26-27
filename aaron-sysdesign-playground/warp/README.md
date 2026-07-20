# warp

Rectifies the combat arena floor in a frame to a fixed 640x640 top-down
view via cv2's perspective warp. Corners are picked by hand: `pick_corners`
opens a window, you click the 4 floor corners, and it warps from there --
automatic detection turned out to be too unreliable across cameras with
different wall thickness, background contrast, and lighting.

Calibrates a key (e.g. tournament + camera, since that pairing is normally
a fixed physical setup) once, but doesn't assume it holds forever:
`review_warp` shows each later match's frame warped with the current
calibration and lets the caller confirm it or trigger `pick_corners`
again, which replaces the calibration from that match onward -- catches a
camera that got bumped or moved mid-tournament instead of silently
reusing a stale warp for every remaining match.

Both windows share one persistent OS window (`WINDOW_NAME`) rather than
opening a new one per match, since a full scrape can mean reviewing
hundreds of them in a row.

The picker window has a 150px clickable black margin around the frame, so
a corner the camera cuts off (common along the near wall) can still be
placed outside the real image instead of being lost. Warping then fills
black anywhere that pulls a pixel from outside the original frame.

Hot-path methods: `warp()`, `review_warp()`. Queryable state: `calibrated_keys`.

Used by `scripts/brettzone_frames.py`, which persists clicked corners in
`manifest.json` so a resumed run only reviews matches it hasn't reached yet.
