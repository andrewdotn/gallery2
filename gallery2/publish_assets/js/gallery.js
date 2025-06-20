function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
           (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function start() {
    const imagesWithVideo = document.querySelectorAll('img[data-has-video="true"]');

    imagesWithVideo.forEach(img => {
        img.addEventListener('click', function () {
            const videoFilename = this.getAttribute('data-video-filename');

            const video = document.createElement('video');
            video.width = img.width;
            video.height = img.height;
            video.src = videoFilename;
            video.controls = !isIOS();
            video.autoplay = true;
            video.className = 'img-fluid';
            video.playsInline = true;

            const container = this.parentNode;
            container.replaceChild(video, this);

            // go back to image when video ends
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
