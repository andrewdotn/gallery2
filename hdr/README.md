I want to be able to take the HDR images that my iPhone captures (HEIC
files with something called [embedded gain maps][1]), resize them, and emit
a file with the same embedded gain map that I can then put on a web page.
It would be nice if I could use a more efficient file format like AVIF or
WEBP but in the end I could only get it working with JPEGs.

It took *days* to get even a partial solution.

I currently get the bright spots showing up as HDR, but:
  - The ICC CICP (aka NCLX) params are getting mangled, e.g., source image
    is P3 but thumbnail comes out BT.2020.
  - There are some parameters like gamma and content boost that I’m just
    guessing at. I think overall brightness gets distorted, but CICP is a
    suspect here as well.

[1]: https://gregbenzphotography.com/hdr-photos/jpg-hdr-gain-maps-in-adobe-camera-raw/

What doesn’t work, or at least what I couldn’t get to work:
  - using heic files on the web—only supported by safari
  - pillow—high-bit-depth images are an issue
    <https://github.com/python-pillow/Pillow/issues/1888>
  - imagemagick—<https://github.com/ImageMagick/ImageMagick/issues/6377>
  - libavif—with a *bunch* of tweaking I got something that worked in
    Preview.app but not Chrome; while avifgainmaputil was useful I
    think I ended up with too many parameters I didn’t understand? This
    could probably be revisited using the params I pass in to
    ultrahdr_app.
  - vips—`vips copy` ignores the gain map
  - libwebp doesn’t have anything for gain maps
  - using standard Swift code, Apple libraries like Image I/O, to open
    HEIC in HDR mode and write out as JPEG; intensity blown out. Also
    even a reduced-size jpeg export from Photos.app, while it does
    preserve HDR, it keeps the original gain map instead of resizing
    it.
      - Image I/O can read AVIF and WEBP, but not write them
      - It’s possible <https://github.com/grapeot/AppleJPEGGainMap>
        works, I found it after getting it working another way
