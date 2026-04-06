(function () {
  var DURATION = 650;

  // ENTER: ensure page is visible (fixes white page on back-button)
  window.addEventListener('pageshow', function () {
    document.body.style.transition = '';
    document.body.style.opacity = '1';
  });

  // MOBILE: only the masonry item closest to screen centre is in colour
  if (window.matchMedia('(max-width: 600px)').matches) {
    setTimeout(function () {
      var items = Array.from(document.querySelectorAll('.masonry-item'));
      if (!items.length) return;

      var activeItem = null;

      function updateColour() {
        var midY = window.scrollY + window.innerHeight / 2;
        var closest = null;
        var closestDist = Infinity;

        items.forEach(function (item) {
          var rect = item.getBoundingClientRect();
          var itemMid = window.scrollY + rect.top + rect.height / 2;
          var dist = Math.abs(itemMid - midY);
          if (dist < closestDist) { closestDist = dist; closest = item; }
        });

        if (closest === activeItem) return;
        activeItem = closest;

        items.forEach(function (item) {
          var media = item.querySelectorAll('img, video');
          var isActive = item === closest;
          media.forEach(function (el) {
            el.style.filter = isActive ? 'grayscale(0)' : 'grayscale(1)';
          });
        });
      }

      window.addEventListener('scroll', updateColour, { passive: true });
      updateColour();
    }, 500);
  }

  // EXIT: fade body content out, then navigate
  document.querySelectorAll('a[href]').forEach(function (a) {
    var href = a.getAttribute('href') || '';
    if (href.startsWith('mailto:') || href.startsWith('#') || href.startsWith('http')) return;

    a.addEventListener('click', function (e) {
      e.preventDefault();
      var target = a.href;
      document.body.style.transition = 'opacity ' + DURATION + 'ms ease-in-out';
      document.body.style.opacity = '0';
      setTimeout(function () { window.location.href = target; }, DURATION);
    });
  });
}());
