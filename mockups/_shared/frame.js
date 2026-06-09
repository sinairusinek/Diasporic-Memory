/* JeckeArchive · shared frame
 * Generic init for timeline, Leaflet map, entity panel, topic chips, highlight toggles,
 * view-mode switcher (reading / side-by-side facsimile / facsimile only), and lightbox.
 *
 * Each demo defines a global object `window.FRAME_DATA` with:
 *   {
 *     timeline: [{year:1932, label:'…', anchor:'#l1', pivot:true}, …],
 *     places:   [{name, lat, lng, kind:'heimat'|'current'|'mention', note}],
 *     entities: [{name, type:'person'|'org'|'family', altname, bio}],
 *     topics:   ['…', …],
 *     ner:      ['place','person','org','date'],     // which NER toggles to show
 *     relevance: true,                                // show "project-relevant" toggle?
 *     views:    ['reading','side-by-side','facsimile'] // which view toggles
 *   }
 */
(function () {

  function makeBtn(opts) {
    var b = document.createElement('button');
    b.type = 'button';
    if (opts.cls) b.className = opts.cls;
    b.textContent = opts.label;
    if (opts.title) b.title = opts.title;
    return b;
  }

  function group(label) {
    var g = document.createElement('span');
    g.className = 'group';
    if (label) {
      var l = document.createElement('span');
      l.className = 'group-label';
      l.textContent = label;
      g.appendChild(l);
    }
    return g;
  }

  window.FrameInit = function () {
    var data = window.FRAME_DATA || {};
    var center = document.querySelector('.frame-center');

    /* ---------- TIMELINE ---------- */
    var tlHost = document.querySelector('.frame-timeline .tl-track');
    if (tlHost && data.timeline && data.timeline.length) {
      var years = data.timeline.map(function (e) { return e.year; });
      var minY = Math.min.apply(null, years), maxY = Math.max.apply(null, years);
      var span = Math.max(1, maxY - minY);
      data.timeline.forEach(function (e) {
        var pct = (e.year - minY) / span;
        var a = document.createElement('a');
        a.className = 'tl-event' + (e.pivot ? ' is-pivot' : '');
        a.href = e.anchor || '#';
        a.style.left = (pct * 100) + '%';
        a.innerHTML = '<span class="tl-year">' + e.year + '</span><span class="tl-label">' + (e.label || '') + '</span>';
        tlHost.appendChild(a);
      });
    }

    /* ---------- MAP ---------- */
    var mapEl = document.getElementById('frame-map');
    if (mapEl && data.places && data.places.length && window.L) {
      var ctr = data.mapCenter || [data.places[0].lat, data.places[0].lng];
      var zm = data.mapZoom || 3;
      var map = L.map(mapEl, { scrollWheelZoom: false, zoomControl: true }).setView(ctr, zm);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OSM',
        maxZoom: 14
      }).addTo(map);
      var bounds = [];
      var pinColor = { heimat: '#8a2418', current: '#2d5a5a', mention: '#6b6354' };
      data.places.forEach(function (p) {
        var c = pinColor[p.kind] || pinColor.mention;
        var icon = L.divIcon({
          className: 'frame-pin',
          html: '<div style="width:12px;height:12px;border-radius:50%;background:' + c + ';border:2px solid #fff;box-shadow:0 0 0 1px ' + c + ', 0 1px 2px rgba(0,0,0,0.3);"></div>',
          iconSize: [12, 12], iconAnchor: [6, 6]
        });
        var marker = L.marker([p.lat, p.lng], { icon: icon }).addTo(map);
        var popup = '<strong>' + p.name + '</strong>';
        if (p.note) popup += '<em>' + p.note + '</em>';
        marker.bindPopup(popup);
        bounds.push([p.lat, p.lng]);
      });
      if (bounds.length > 1) {
        try { map.fitBounds(bounds, { padding: [22, 22] }); } catch (_) {}
      }
    }

    /* ---------- ENTITIES ---------- */
    var entHost = document.querySelector('.frame-entities .ent-list');
    if (entHost && data.entities) {
      data.entities.forEach(function (e) {
        var li = document.createElement('li');
        li.className = 'ent type-' + (e.type || 'person');
        li.innerHTML =
          '<span class="type">' + (e.type || 'person') + '</span>' +
          '<span class="nm">' + e.name + (e.altname ? ' <em>' + e.altname + '</em>' : '') + '</span>' +
          (e.bio ? '<div class="bio">' + e.bio + '</div>' : '');
        entHost.appendChild(li);
      });
    }

    /* ---------- TOPIC CHIPS ---------- */
    var topicHost = document.querySelector('.frame-topics .topic-list');
    if (topicHost && data.topics) {
      data.topics.forEach(function (t) {
        var label = typeof t === 'string' ? t : t.label;
        var li = document.createElement('li');
        li.textContent = label;
        li.dataset.topic = label.toLowerCase();
        topicHost.appendChild(li);
      });
    }

    /* ---------- HIGHLIGHT + VIEW BAR ---------- */
    var bar = document.querySelector('.frame-highlight-bar');
    if (!bar || !center) return;

    // wipe whatever's in the bar after the static .hl-label so we can compose
    // (the demo provides only the leading `<span class="hl-label">highlight:</span>` text node)
    Array.prototype.slice.call(bar.querySelectorAll('button, .group:not(:first-child)'))
      .forEach(function (n) { n.remove(); });

    // -- NER group
    var ner = data.ner || ['place', 'person', 'date'];
    if (ner.length) {
      var gNer = group('NER:');
      ner.forEach(function (kind) {
        var btn = makeBtn({ label: kind, cls: 'ner-btn', title: 'Show ' + kind + ' entities' });
        btn.addEventListener('click', function () {
          var cls = 'show-' + kind;
          center.classList.toggle(cls);
          btn.classList.toggle('is-on', center.classList.contains(cls));
        });
        gNer.appendChild(btn);
      });
      bar.appendChild(gNer);
    }

    // -- Relevance toggle (project-significant sentences)
    if (data.relevance !== false) {
      var gRel = group('Project:');
      var btnR = makeBtn({ label: 'relevant sentences', cls: 'rel-btn', title: 'Highlight project-relevant sentences (Heimat-axis)' });
      btnR.addEventListener('click', function () {
        center.classList.toggle('show-relevant');
        btnR.classList.toggle('is-on', center.classList.contains('show-relevant'));
      });
      gRel.appendChild(btnR);
      bar.appendChild(gRel);
    }

    // -- View modes
    var views = data.views || ['reading', 'side-by-side', 'facsimile'];
    if (views.length > 1) {
      var gView = group('View:');
      var viewBtns = [];
      views.forEach(function (v) {
        var btn = makeBtn({ label: v, cls: 'view-btn', title: 'Switch to ' + v + ' view' });
        btn.dataset.view = v;
        if (v === 'reading') btn.classList.add('is-on');
        btn.addEventListener('click', function () {
          viewBtns.forEach(function (b) { b.classList.remove('is-on'); });
          btn.classList.add('is-on');
          center.classList.remove('view-sbs', 'view-facs');
          if (v === 'side-by-side') center.classList.add('view-sbs');
          else if (v === 'facsimile') center.classList.add('view-facs');
        });
        viewBtns.push(btn);
        gView.appendChild(btn);
      });
      bar.appendChild(gView);
    }

    /* ---------- LIGHTBOX (facsimile zoom) ---------- */
    var lb = document.createElement('div');
    lb.className = 'frame-lightbox';
    lb.innerHTML = '<img>';
    document.body.appendChild(lb);
    lb.addEventListener('click', function () { lb.classList.remove('open'); });
    document.addEventListener('click', function (e) {
      var img = e.target.closest('.facsimile img');
      if (!img) return;
      lb.querySelector('img').src = img.src;
      lb.classList.add('open');
    });

    /* ---------- topic chip filter (decorative for now) ---------- */
    document.querySelectorAll('.frame-topics .topic-list li').forEach(function (li) {
      li.addEventListener('click', function () { li.classList.toggle('is-active'); });
    });
  };
})();
