Based on [django-boilerplate], a more modern replacement of my ancient (2005ish)
GalleryMaker (C#+GDI) code, this time as a django webapp.

Very much a work-in-progress, bad UI, but basic functionality is there.
 1. Create a new gallery in the UI.
 2. `./manage.py importimages $IMAGE_FOLDER $GALLERY_ID` to load photos
       - All the photos have to be in that directory
       - You can run this again when you add new photos
 3. Click into gallery and add captions in browser.
 4. Re-order images by using the Admin button :/
 5. Then `./manage.py buildgallery` to emit standalone html in the `publish` folder.

I guess the main new features over GalleryMaker are:
  - Supports video
  - Supports live photos (heic+mov file with same basename)

Not great code, but at least [Junie] was fast—until I exceeded some limits that
is. I guess they don’t expect you to run it in several IDEs in parallel for 4+
straight hours?

![](v0-ui.webp)

[django-boilerplate]: https://github.com/andrewdotn/django-boilerplate
[Junie]: https://www.jetbrains.com/junie/
