import App from './App'

global.jQuery = require('jquery')
require('bootstrap')
import 'bootstrap/dist/css/bootstrap.css'
import 'leaflet/dist/leaflet.css'
import './app.css'

jQuery(document).ready(() => {
	let app = new App()
})
