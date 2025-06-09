function start() {
// Find all images with data-has-video attribute
    const imagesWithVideo = document.querySelectorAll('img[data-has-video="true"]');

    imagesWithVideo.forEach(img => {
        img.addEventListener('click', function () {
            const videoFilename = `media/${this.getAttribute('data-video-filename')}`;

            // Create video element
            const video = document.createElement('video');
            video.width = img.width;
            video.height = img.height;
            video.src = videoFilename;
            video.controls = true;
            video.autoplay = true;
            video.className = 'img-fluid';

            // Replace the image with the video
            const container = this.parentNode;
            container.replaceChild(video, this);

            // Add event listener to go back to image when video ends
            video.addEventListener('ended', function () {
                container.replaceChild(img, video);
            });
        });
    })
}

// DOMContentLoaded might not fire with an async script
// https://stackoverflow.com/questions/39993676/code-inside-domcontentloaded-event-not-working
if (document.readyState !== "loading") {
  start();
} else {
  document.addEventListener("DOMContentLoaded", start);
}
