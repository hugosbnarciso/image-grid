document.addEventListener("DOMContentLoaded", function () {
  // Get the photo container element
  var photoContainer = document.getElementById("photo-container");

  // Initialize the Dragula library on the photo container
  dragula([photoContainer]);

  // Prevent the default click action (opening the image in a new page) on the images
  photoContainer.addEventListener("click", function (event) {
    event.preventDefault();
  });
});