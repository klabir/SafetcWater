import appdaemon.plugins.hass.hassapi as hass
import requests
from datetime import datetime

class SafetecVolClass(hass.Hass):
    def initialize(self):
       # self.log("SafetecVolClass is initialized")
        self.run_every(self.make_api_call, "now", 30)

    def make_api_call(self, kwargs):
        url3 = "http://192.168.1.81:5333/trio/set/adm/(2)f"
        url = "http://192.168.1.81:5333/trio/get/vol"
        output_file = "/homeassistant/appdaemon/output.txt"

     #   self.log("Before API call")

        try:
            # Set ADM
            response3 = requests.get(url3)
       #     self.log(f"Admin call response: {response3.status_code}")

            # Get VOL
            response = requests.get(url)
        #    self.log(f"Get VOL call response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                value = int(data.get("getVOL"))

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                output_text = f"{timestamp}: {value}"

                with open(output_file, "a") as file:
                    file.write(output_text + "\n")

           #     self.log(f"getVOL written: {output_text}")
            else:
                self.log(f"Error with GETVOL request. Status code: {response.status_code}")

        except requests.RequestException as e:
            self.log(f"Network error occurred: {e}")
        except Exception as e:
            self.log(f"Unexpected error occurred: {e}")
