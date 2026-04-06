/**
 * Masonry layout — handles both .project-grid (project pages)
 * and .masonry-grid (homepage).
 *
 * Two algorithms, selected per grid via rowAligned:
 *
 *   rowAligned: true  — items placed left-to-right in groups of `cols`.
 *     Every row starts at the same top across all columns, so horizontal
 *     lines are clean. Items within a row can still differ in height,
 *     giving the staggered look without misaligned row tops.
 *
 *   rowAligned: false — "shortest column" algorithm. Each item goes into
 *     whichever column is shortest at that moment. More organic stagger
 *     but row tops can drift out of alignment.
 */
(function () {
  'use strict';

  var GRIDS = [
    {
      selector:     '.project-grid',
      itemSelector: '.project-block',
      gap:          140,
      rowAligned:   true,          /* aligned row tops for project pages */
      getCols: function (w) {
        if (w < 600) return 1;
        if (w < 900) return 2;
        return 3;
      }
    },
    {
      selector:     '.masonry-grid',
      itemSelector: '.masonry-item',
      gap:          140,
      rowAligned:   false,         /* organic stagger for homepage */
      getCols: function (w) {
        if (w < 600) return 1;
        if (w < 900) return 2;
        return 3;
      }
    }
  ];

  function layout(grid, config) {
    var width = grid.offsetWidth;

    /* CSS grid may not have computed dimensions yet — retry next frame */
    if (!width) {
      requestAnimationFrame(function () { layout(grid, config); });
      return;
    }

    var items = Array.from(grid.querySelectorAll(config.itemSelector));
    var cols  = config.getCols(width);
    var GAP   = config.gap;
    var colW  = Math.floor((width - (cols - 1) * GAP) / cols);

    /* Pass 1 — set widths so items reflow to their correct heights */
    items.forEach(function (item) {
      item.style.position = 'absolute';
      item.style.width    = colW + 'px';
    });

    /* Pass 2 — measure heights and place items.
       setTimeout(100) gives the browser a full 100 ms to reflow images
       to their new column width before we read offsetHeight. */
    setTimeout(function () {
      var tops = new Array(cols).fill(0);

      if (config.rowAligned) {
        /* ── Row-aligned: process cols items at a time ── */
        for (var i = 0; i < items.length; i += cols) {
          var rowItems = items.slice(i, Math.min(i + cols, items.length));

          /* All items in this row share the same top = current max */
          var rowTop = Math.max.apply(null, tops);

          rowItems.forEach(function (item, j) {
            item.style.top  = rowTop + 'px';
            item.style.left = (j * (colW + GAP)) + 'px';
            tops[j] = rowTop + item.offsetHeight + GAP;
          });
        }
      } else {
        /* ── Shortest-column: each item goes into the shortest column ── */
        items.forEach(function (item) {
          var col  = tops.indexOf(Math.min.apply(null, tops));
          var left = col * (colW + GAP);
          var top  = tops[col];

          item.style.top  = top  + 'px';
          item.style.left = left + 'px';

          tops[col] += item.offsetHeight + GAP;
        });
      }

      /* Stretch container so elements below it clear correctly */
      grid.style.height     = (Math.max.apply(null, tops) - GAP) + 'px';
      grid.style.visibility = 'visible';
    }, 100);
  }

  function initGrid(config) {
    var grid = document.querySelector(config.selector);
    if (!grid) return;

    grid.style.position   = 'relative';
    grid.style.visibility = 'hidden';

    var imgs   = Array.from(grid.querySelectorAll('img'));
    var vids   = Array.from(grid.querySelectorAll('video'));
    var total  = imgs.length + vids.length;
    var loaded = 0;

    function check() {
      loaded += 1;
      if (loaded >= total) layout(grid, config);
    }

    if (total === 0) { layout(grid, config); return; }

    imgs.forEach(function (img) {
      if (img.complete) {
        check();
      } else {
        img.addEventListener('load',  check);
        img.addEventListener('error', check);
      }
    });

    vids.forEach(function (vid) {
      if (vid.readyState >= 1) { /* HAVE_METADATA or better */
        check();
      } else {
        vid.addEventListener('loadedmetadata', check);
        vid.addEventListener('error',          check);
      }
    });
  }

  /* Re-layout on resize (debounced 120 ms) */
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      GRIDS.forEach(function (config) {
        var grid = document.querySelector(config.selector);
        if (grid) { grid.style.visibility = 'hidden'; layout(grid, config); }
      });
    }, 120);
  });

  function init() {
    GRIDS.forEach(function (config) { initGrid(config); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
