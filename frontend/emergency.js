// SOS Button functionality
const sosButton = document.getElementById('sosButton');
const sosModal = document.getElementById('sosModal');
const closeModal = document.getElementsByClassName('close')[0];
const locationInfo = document.getElementById('locationInfo');

// SOS Button Click
sosButton.addEventListener('click', function() {
    sosModal.style.display = 'block';
    
    // Get user location
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const lat = position.coords.latitude.toFixed(6);
                const lon = position.coords.longitude.toFixed(6);
                
                locationInfo.innerHTML = `
                    <p><strong>📍 Your Location:</strong></p>
                    <p>Latitude: ${lat}</p>
                    <p>Longitude: ${lon}</p>
                    <p><small>Share this with emergency services</small></p>
                `;
            },
            function(error) {
                locationInfo.innerHTML = `
                    <p>⚠️ Unable to get location</p>
                    <p><small>Please enable location services</small></p>
                `;
            }
        );
    } else {
        locationInfo.innerHTML = `
            <p>⚠️ Geolocation not supported</p>
        `;
    }
});

// Close modal
closeModal.onclick = function() {
    sosModal.style.display = 'none';
}

window.onclick = function(event) {
    if (event.target == sosModal) {
        sosModal.style.display = 'none';
    }
}

// Make phone numbers clickable on mobile
document.querySelectorAll('.contact-number').forEach(function(element) {
    element.addEventListener('click', function(e) {
        console.log('Calling:', this.textContent);
    });
});
