(() => {
  const mapElement = document.querySelector("[data-trip-map]");
  const tripEventsElement = document.getElementById("trip-map-events");
  const itineraryEventsElement = document.getElementById("itinerary-map-events");
  const itineraryToggle = document.querySelector("[data-itinerary-toggle]");
  const statusElement = document.querySelector("[data-map-status]");

  if (!mapElement) return;
  if (!window.maplibregl) {
    if (statusElement) statusElement.textContent = "The map library could not be loaded. Check your connection and try again.";
    return;
  }

  const tripEvents = tripEventsElement ? JSON.parse(tripEventsElement.textContent) : [];
  const itineraryEvents = itineraryEventsElement ? JSON.parse(itineraryEventsElement.textContent) : [];
  const mapMode = mapElement.dataset.mapMode || "trip";
  const mapEvents = mapMode === "itinerary" ? itineraryEvents : tripEvents;
  const coordinatesFor = (events) => events.map((event) => [event.lng, event.lat]);
  const tripCoordinates = coordinatesFor(tripEvents);
  const itineraryCoordinates = coordinatesFor(itineraryEvents);
  const allCoordinates = [...tripCoordinates, ...itineraryCoordinates];
  if (!allCoordinates.length) return;

  const map = new maplibregl.Map({
    container: mapElement,
    style: "https://tiles.openfreemap.org/styles/positron",
    center: allCoordinates[0],
    zoom: allCoordinates.length === 1 ? 9 : 2,
  });

  map.addControl(new maplibregl.NavigationControl(), "top-right");
  map.addControl(new maplibregl.FullscreenControl(), "top-right");

  const mapDisclosure = mapElement.closest("[data-map-disclosure]");
  if (mapDisclosure) {
    mapDisclosure.addEventListener("toggle", () => {
      if (mapDisclosure.open) requestAnimationFrame(() => map.resize());
    });
  }

  map.on("load", () => {
    if (itineraryEvents.length > 1) {
      map.addSource("itinerary-route", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: itineraryCoordinates },
        },
      });
      map.addLayer({
        id: "itinerary-route-line",
        type: "line",
        source: "itinerary-route",
        paint: { "line-color": "#a98208", "line-opacity": 0.9, "line-width": 3 },
        layout: { visibility: itineraryToggle && !itineraryToggle.checked ? "none" : "visible" },
      });
    }

    if (mapMode !== "itinerary" && tripEvents.length > 1) {
      map.addSource("trip-route", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: tripCoordinates },
        },
      });
      map.addLayer({
        id: "trip-route-line",
        type: "line",
        source: "trip-route",
        paint: { "line-color": "#b5532c", "line-opacity": 0.9, "line-width": 3 },
      });
    }

    const addMarkers = (events, markerClass, visibilityToggle) => events.forEach((event, index) => {
      const coordinates = coordinatesFor(events);
      const markerElement = document.createElement("div");
      markerElement.className = markerClass;
      markerElement.textContent = String(index + 1);
      const layerTieBreak = markerClass === "trip-map-marker" ? 1 : 0;
      markerElement.style.setProperty("--map-marker-z-index", String(10000 - (index + 1) * 2 + layerTieBreak));
      markerElement.setAttribute("aria-label", `${event.date} - ${event.title}`);
      markerElement.hidden = visibilityToggle ? !visibilityToggle.checked : false;

      const popupContent = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = event.title;
      const date = document.createElement("p");
      date.textContent = event.date;
      popupContent.append(title, date);
      if (event.url) {
        const link = document.createElement("a");
        link.href = event.url;
        link.textContent = "Open event";
        popupContent.append(link);
      }

      new maplibregl.Marker({ element: markerElement })
        .setLngLat(coordinates[index])
        .setPopup(new maplibregl.Popup({ offset: 18 }).setDOMContent(popupContent))
        .addTo(map);
    });

    if (mapMode === "itinerary") {
      addMarkers(mapEvents, "itinerary-map-marker");
    } else {
      addMarkers(itineraryEvents, "itinerary-map-marker", itineraryToggle);
      if (itineraryToggle) {
        itineraryToggle.addEventListener("change", () => {
          mapElement.querySelectorAll(".itinerary-map-marker").forEach((marker) => {
            marker.hidden = !itineraryToggle.checked;
          });
          if (itineraryEvents.length > 1) {
            map.setLayoutProperty("itinerary-route-line", "visibility", itineraryToggle.checked ? "visible" : "none");
          }
        });
      }
    }
    addMarkers(tripEvents, "trip-map-marker");

    if (allCoordinates.length > 1) {
      const bounds = allCoordinates.reduce(
        (result, coordinate) => result.extend(coordinate),
        new maplibregl.LngLatBounds(allCoordinates[0], allCoordinates[0]),
      );
      map.fitBounds(bounds, { padding: 48, maxZoom: 12 });
    }

    if (statusElement) {
      statusElement.textContent = mapMode === "itinerary"
        ? `${itineraryEvents.length} itinerary destinations shown.`
        : `${tripEvents.length} trip event locations and ${itineraryEvents.length} itinerary destinations shown.`;
    }
  });

  map.on("error", () => {
    if (statusElement) statusElement.textContent = "The map could not be loaded. Check your connection and try again.";
  });
})();