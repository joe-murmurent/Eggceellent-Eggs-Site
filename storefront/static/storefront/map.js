(() => {
  const mapElement = document.querySelector("[data-trip-map]");
  const eventsElement = document.getElementById("trip-map-events");
  const statusElement = document.querySelector("[data-map-status]");

  if (!mapElement || !eventsElement) return;
  if (!window.maplibregl) {
    if (statusElement) statusElement.textContent = "The map library could not be loaded. Check your connection and try again.";
    return;
  }

  const events = JSON.parse(eventsElement.textContent);
  const coordinates = events.map((event) => [event.lng, event.lat]);
  const map = new maplibregl.Map({
    container: mapElement,
    style: "https://tiles.openfreemap.org/styles/positron",
    center: coordinates[0],
    zoom: events.length === 1 ? 9 : 2,
  });

  map.addControl(new maplibregl.NavigationControl(), "top-right");
  map.addControl(new maplibregl.FullscreenControl(), "top-right");

  map.on("load", () => {
    if (events.length > 1) {
      map.addSource("trip-route", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates },
        },
      });
      map.addLayer({
        id: "trip-route-line",
        type: "line",
        source: "trip-route",
        paint: { "line-color": "#b5532c", "line-opacity": 0.9, "line-width": 3 },
      });
    }

    events.forEach((event, index) => {
      const markerElement = document.createElement("div");
      markerElement.className = "trip-map-marker";
      markerElement.textContent = String(index + 1);
      markerElement.setAttribute("aria-label", `${event.date} - ${event.title}`);

      const popupContent = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = event.title;
      const date = document.createElement("p");
      date.textContent = event.date;
      const link = document.createElement("a");
      link.href = event.url;
      link.textContent = "Open event";
      popupContent.append(title, date, link);

      new maplibregl.Marker({ element: markerElement })
        .setLngLat(coordinates[index])
        .setPopup(new maplibregl.Popup({ offset: 18 }).setDOMContent(popupContent))
        .addTo(map);
    });

    if (events.length > 1) {
      const bounds = coordinates.reduce(
        (result, coordinate) => result.extend(coordinate),
        new maplibregl.LngLatBounds(coordinates[0], coordinates[0]),
      );
      map.fitBounds(bounds, { padding: 48, maxZoom: 12 });
    }

    if (statusElement) statusElement.textContent = `${events.length} locations connected in event-date order.`;
  });

  map.on("error", () => {
    if (statusElement) statusElement.textContent = "The map could not be loaded. Check your connection and try again.";
  });
})();