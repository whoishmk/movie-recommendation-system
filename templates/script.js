document.addEventListener("DOMContentLoaded", () => {
    const carousel = document.querySelector(".carousel");
    const scrollLeft = document.querySelector(".scroll-left");
    const scrollRight = document.querySelector(".scroll-right");
  
    // Scroll left
    scrollLeft.addEventListener("click", () => {
      carousel.scrollBy({
        left: -300,
        behavior: "smooth",
      });
    });
  
    // Scroll right
    scrollRight.addEventListener("click", () => {
      carousel.scrollBy({
        left: 300,
        behavior: "smooth",
      });
    });
  });
  