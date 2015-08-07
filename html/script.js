$(function() {
    // we'll be populating this with our GeoJSON layers
    var routes = {
        "Valhalla": null,
        "OSRM": null,
        "GMaps": null
    };

    var map = L.map('map').setView([51.500829999995766, -0.12203999999842599], 12);
    var bg = L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
        attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="http://mapbox.com">Mapbox</a>',
        maxZoom: 16,
        id: 'urschrei.n35fc4ge',
        accessToken: 'pk.eyJ1IjoidXJzY2hyZWkiLCJhIjoiVXN5WkVYbyJ9.87LXqCJ6CuZsfrJ5hcijpw'
    }).addTo(map);

    var valStyle = {
        "color": "#008080",
        "weight": .65,
        "opacity": 0.5
    };

    var osrmStyle = {
        "color": "#E87600",
        "weight": .65,
        "opacity": 0.5
    };

    var gmapsStyle = {
        "color": "#9B30FF",
        "weight": .65,
        "opacity": 0.5
    };

    $.getJSON("valhalla_geojson.json", function(data) {
        routes.Valhalla = L.geoJson(data, {
            onEachFeature: function (feature, layer) {
                layer.bindPopup(feature.properties.name);
            }
        });
        routes.Valhalla.setStyle(valStyle);
        routes.Valhalla.addTo(map);
    });

    $.getJSON("osrm_geojson.json", function(data) {
        routes.OSRM = L.geoJson(data, {
            onEachFeature: function (feature, layer) {
                layer.bindPopup(feature.properties.name);
            }
        });
        routes.OSRM.setStyle(osrmStyle);
        routes.OSRM.addTo(map);
    });

    $.getJSON("gmaps_geojson.json", function(data) {
        routes.GMaps = L.geoJson(data, {
            onEachFeature: function (feature, layer) {
                layer.bindPopup(feature.properties.name);
            }
        });
        routes.GMaps.setStyle(gmapsStyle);
        routes.GMaps.addTo(map);
        // this is the third layer, so attach it to the map
        L.control.layers(null, routes).addTo(map);
    });
});
