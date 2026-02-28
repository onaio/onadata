// Get the raw JSON data passed from Django
let rawJsonData = document.getElementById('json-data').textContent;

// Parse the JSON string into a JavaScript object
let jsonData = JSON.parse(rawJsonData);

// Display the JSON data in a formatted way
document.getElementById('json-data').textContent = JSON.stringify(jsonData, null, 2);
