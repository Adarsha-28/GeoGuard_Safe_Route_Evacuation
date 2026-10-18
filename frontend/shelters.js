// Chennai Flood Relief Shelters Database
const shelters = [
    // Central Chennai
    { name: "Corporation Primary School, T. Nagar", lat: 13.0418, lng: 80.2341, capacity: 500, facilities: ["Water", "Food", "Medical"], contact: "044-2434-5678" },
    { name: "Anna Nagar Community Hall", lat: 13.0850, lng: 80.2101, capacity: 300, facilities: ["Water", "Food", "Toilets"], contact: "044-2615-4321" },
    { name: "Nungambakkam High School", lat: 13.0569, lng: 80.2425, capacity: 400, facilities: ["Water", "Food", "Medical", "Toilets"], contact: "044-2827-9876" },
    { name: "Egmore Relief Center", lat: 13.0732, lng: 80.2609, capacity: 350, facilities: ["Water", "Food", "Medical"], contact: "044-2819-5432" },
    
    // South Chennai
    { name: "Adyar Kalyana Mandapam", lat: 13.0067, lng: 80.2570, capacity: 600, facilities: ["Water", "Food", "Medical", "Toilets"], contact: "044-2441-2345" },
    { name: "Velachery Community Center", lat: 12.9750, lng: 80.2210, capacity: 450, facilities: ["Water", "Food", "Toilets"], contact: "044-2266-7890" },
    { name: "Guindy Marriage Hall", lat: 13.0067, lng: 80.2206, capacity: 500, facilities: ["Water", "Food", "Medical"], contact: "044-2235-4567" },
    { name: "Mylapore Temple Hall", lat: 13.0339, lng: 80.2619, capacity: 400, facilities: ["Water", "Food", "Toilets"], contact: "044-2464-8901" },
    { name: "Kotturpuram School", lat: 13.0200, lng: 80.2450, capacity: 300, facilities: ["Water", "Food"], contact: "044-2441-3456" },
    { name: "Thiruvanmiyur Relief Camp", lat: 12.9820, lng: 80.2590, capacity: 350, facilities: ["Water", "Food", "Medical"], contact: "044-2441-7890" },
    
    // Coastal Areas
    { name: "Besant Nagar Community Hall", lat: 13.0001, lng: 80.2668, capacity: 400, facilities: ["Water", "Food", "Medical", "Toilets"], contact: "044-2445-6789" },
    { name: "Sholinganallur Relief Center", lat: 12.9010, lng: 80.2279, capacity: 500, facilities: ["Water", "Food", "Medical"], contact: "044-2450-1234" },
    { name: "Neelankarai School", lat: 12.9490, lng: 80.2590, capacity: 300, facilities: ["Water", "Food"], contact: "044-2449-5678" },
    
    // West Chennai
    { name: "Porur Community Center", lat: 13.0381, lng: 80.1570, capacity: 400, facilities: ["Water", "Food", "Medical", "Toilets"], contact: "044-2476-2345" },
    { name: "Ashok Nagar Marriage Hall", lat: 13.0358, lng: 80.2101, capacity: 350, facilities: ["Water", "Food", "Toilets"], contact: "044-2489-6789" },
    { name: "KK Nagar Relief Camp", lat: 13.0381, lng: 80.2020, capacity: 300, facilities: ["Water", "Food"], contact: "044-2474-3456" },
    { name: "Vadapalani Temple Hall", lat: 13.0504, lng: 80.2121, capacity: 450, facilities: ["Water", "Food", "Medical"], contact: "044-2480-7890" },
    
    // North Chennai
    { name: "Perambur Relief Center", lat: 13.1143, lng: 80.2378, capacity: 500, facilities: ["Water", "Food", "Medical", "Toilets"], contact: "044-2662-1234" },
    { name: "Madhavaram Community Hall", lat: 13.1482, lng: 80.2314, capacity: 400, facilities: ["Water", "Food", "Toilets"], contact: "044-2552-5678" },
    { name: "Ambattur School", lat: 13.1143, lng: 80.1548, capacity: 450, facilities: ["Water", "Food", "Medical"], contact: "044-2656-9012" },
    { name: "Avadi Relief Camp", lat: 13.1067, lng: 80.1018, capacity: 350, facilities: ["Water", "Food"], contact: "044-2666-3456" },
    
    // South Suburbs
    { name: "Tambaram Corporation School", lat: 12.9249, lng: 80.1000, capacity: 600, facilities: ["Water", "Food", "Medical", "Toilets"], contact: "044-2226-7890" },
    { name: "Chromepet Community Center", lat: 12.9516, lng: 80.1462, capacity: 400, facilities: ["Water", "Food", "Toilets"], contact: "044-2235-1234" },
    { name: "Pallikaranai Relief Center", lat: 12.9450, lng: 80.2050, capacity: 350, facilities: ["Water", "Food", "Medical"], contact: "044-2266-5678" },
    { name: "Perungudi School", lat: 12.9610, lng: 80.2440, capacity: 300, facilities: ["Water", "Food"], contact: "044-2496-9012" }
];

// Calculate distance between two coordinates (in km)
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Find nearest shelters
function findNearestShelters(lat, lng, count = 3) {
    const sheltersWithDistance = shelters.map(shelter => ({
        ...shelter,
        distance: calculateDistance(lat, lng, shelter.lat, shelter.lng)
    }));
    
    return sheltersWithDistance.sort((a, b) => a.distance - b.distance).slice(0, count);
}

// Get shelter by area name
function getSheltersByArea(areaName) {
    // Simple matching based on area name in shelter name
    return shelters.filter(shelter => 
        shelter.name.toLowerCase().includes(areaName.toLowerCase())
    );
}
