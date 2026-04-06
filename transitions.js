(function () {
  var DURATION = 650;

  // ENTER: ensure page is visible (fixes white page on back-button)
  window.addEventListener('pageshow', function () {
    document.body.style.transition = '';
    document.body.style.opacity = '1';
  });

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
