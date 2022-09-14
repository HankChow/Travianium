import json
import os
import re

import requests

from bs4 import BeautifulSoup


class Travian(object):
    
    def __init__(self):
        self.username = os.getenv("tr_username")
        self.password = os.getenv("tr_password")
        self.server = os.getenv("tr_server")
        self.session = requests.session()
        self.mapping = {
            "resources_short": ["lumber", "clay", "iron", "crop"],
            "resources_long": ["lumber", "clay", "iron", "crop", "free_crop"],
        }
        self.urls = {
            "login": "/api/v1/auth/login",
            "dorf1": "/dorf1.php",
            "dorf2": "/dorf2.php",
            "tile": "/api/v1/map/tile-details",
            "build": "/build.php",
        }
        self.selectors = {
            "dorf1_player_name": "div#sidebarBoxActiveVillage div.playerName",
            "dorf1_stock": "div#stockBar",
            "dorf1_production": "div.villageInfobox table#production tbody tr",
            "dorf1_resource_fields": "div#resourceFieldContainer a.level",
            "dorf1_troops": "div.villageInfobox table#troops tbody tr",
            "dorf1_movements": "div.villageInfobox table#movements",
            "dorf1_building_list": "div.buildingList ul li",
            "dorf2_buildings": "div#villageContent div",
        }
        self.logged_in = self.login()
        
    def login(self):
        nonce_json = self.session.post("https://{server}{url}".format(
            server=self.server,
            url=self.urls["login"]
        ), json={
            "name": self.username,
            "password": self.password,
            "w": "1440:900",
            "mobileOptimizations": False
        }).json()
        nonce = nonce_json.get("nonce")
        if nonce:
            token_json = self.session.post("https://{server}/api/v1/auth/{nonce}".format(
                server=self.server,
                nonce=nonce
            )).json()
            token = token_json.get("token")
            self.token = token
            test_login = self.session.get("https://{server}{url}".format(
                server=self.server,
                url=self.urls["dorf1"]
            ))
            soup = BeautifulSoup(test_login.text, "html.parser")
            if soup.select(self.selectors["dorf1_player_name"]) and (soup.select(self.selectors["dorf1_player_name"])[0].string == self.username):
                return True
        return False
            
    def get_info(self):
        info = {}
        # dorf1
        dorf1_page = self.session.get("https://{server}{url}".format(
            server=self.server,
            url=self.urls["dorf1"]
        ))
        soup_dorf1 = BeautifulSoup(dorf1_page.text, "html.parser")
        stock = soup_dorf1.select(self.selectors["dorf1_stock"])[0]
        info["stock"] = {}
        info["stock"]["warehouse_capacity"] = int(stock.select(".warehouse .capacity")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        info["stock"]["lumber"] = int(stock.select(".warehouse .stockBarButton")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        info["stock"]["clay"] = int(stock.select(".warehouse .stockBarButton")[1].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        info["stock"]["iron"] = int(stock.select(".warehouse .stockBarButton")[2].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        info["stock"]["granary_capacity"] = int(stock.select(".granary .capacity")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        info["stock"]["crop"] = int(stock.select(".granary .stockBarButton")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        info["stock"]["free_crop"] = int(stock.select(".granary .stockBarButton")[1].get_text().encode('ascii', 'ignore').decode('unicode_escape').replace(",", ""))
        production = soup_dorf1.select(self.selectors["dorf1_production"])
        info["production"] = {self.mapping["resources_short"][index]: int(_.select("td.num")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape')) for index, _ in enumerate(production[:len(self.mapping["resources_short"])])}
        resource_fields = soup_dorf1.select(self.selectors["dorf1_resource_fields"])
        info["resource_fields"] = []
        for resource_field in resource_fields:
            rf = {
                "id": int([re.match("buildingSlot(\d+)", _).group(1) for _ in resource_field.get("class") if re.match("buildingSlot\d+", _)][0]),
                "resource_id": int([re.match("gid(\d+)", _).group(1) for _ in resource_field.get("class") if re.match("gid\d+", _)][0]),
                "level": int([re.match("level(\d+)", _).group(1) for _ in resource_field.get("class") if re.match("level\d+", _)][0])
            }
            if rf["resource_id"] == 1:
                rf["name"] = "lumber"
            elif rf["resource_id"] == 2:
                rf["name"] = "clay"
            elif rf["resource_id"] == 3:
                rf["name"] = "iron"
            elif rf["resource_id"] == 4:
                rf["name"] = "corn"
            info["resource_fields"].append(rf)
        troops = soup_dorf1.select(self.selectors["dorf1_troops"])
        if troops[0].select("td.noTroops"):
            info["troops"] = {}
        else:
            info["troops"] = [{
                "name": _.select("td.un")[0].get_text(),
                "count": int(_.select("td.num")[0].get_text())
            } for _ in troops]
        movements = soup_dorf1.select(self.selectors["dorf1_movements"])
        if movements:
            info["movements"] = {
                "outgoing": [], 
                "incoming": []
            }
            for movement in movements:
                direction = None
                if "Incoming" in movement.select("tr")[0].get_text():
                    direction = "incoming"
                if "Outgoing" in movement.select("tr")[0].get_text():
                    direction = "outgoing"
                if direction:
                    info["movements"][direction] = [{
                        "type": _.select("div.mov")[0].get_text().split()[1],
                        "count": int(_.select("div.mov")[0].get_text().split()[0]),
                        "duration": _.select("div.dur_r span.timer")[0].get_text()
                    } for _ in movement.select("tr") if _.select("div.mov") and _.select("div.dur_r span.timer")]
        building_list = soup_dorf1.select(self.selectors["dorf1_building_list"])
        if building_list:
            info["building_list"] = []
            for bl in building_list:
                info["building_list"].append({
                    "name": list(bl.select("div.name")[0].strings)[0].strip(),
                    "level": bl.select("div.name span.lvl")[0].get_text(),
                    "duration": bl.select("div.buildDuration span.timer")[0].get_text()
                })
        # dorf2
        dorf2_page = self.session.get("https://{server}{url}".format(
            server=self.server,
            url=self.urls["dorf2"]
        ))
        soup_dorf2 = BeautifulSoup(dorf2_page.text, "html.parser")
        buildings = soup_dorf2.select(self.selectors["dorf2_buildings"])
        info["buildings"] = []
        for building in buildings:
            b = {
                "id": int(building.get("data-aid")),
                "building_id": int(building.get("data-gid")),
                "name": building.get("data-name"),
                "level": int(building.select("a")[0]["data-level"]) if building.get("data-name") else 0
            }
            info["buildings"].append(b)
        return info
        
    def get_tile_info(self, x, y):
        tile_json = self.session.post("https://{server}{url}".format(
            server=self.server,
            url=self.urls["tile"]
        ), json={
            "x": x,
            "y": y
        }, headers={
            "Authorization": "Bearer {}".format(self.token)
        }).json()
        tile_html = tile_json["html"]
        soup_tile = BeautifulSoup(tile_html, "html.parser")
        # return soup_tile
        tile_info = {}
        if not soup_tile.select("div#map_details"):
            tile_info["type"] = "wilderness"
        else:
            map_details = soup_tile.select("div#map_details")[0]
            if "oasis" in soup_tile.select("div#tileDetails")[0].get("class"):
                tile_info["type"] = "oasis"
                tile_info["distribution"] = [{
                    "resource": _.select("td.desc")[0].get_text(),
                    "value": _.select("td.val")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape')
                } for _ in map_details.select("table#distribution tr") if _.select("td.desc") and _.select("td.val")]
                tile_info["troops"] = [{
                    "name": _.select("td.desc")[0].get_text(),
                    "count": _.select("td.val")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape')
                } for _ in map_details.select("table#troop_info tr") if _.select("td.desc") and _.select("td.val")]
            elif "village" in soup_tile.select("div#tileDetails")[0].get("class"):
                resource_field_types = ["lumber", "clay", "iron", "crop"]
                if map_details.select("table#village_info"):
                    tile_info["resource_fields"] = [{
                        "type": resource_field_types[index],
                        "count": int(_.get_text())
                    } for index, _ in enumerate(map_details.select("table#distribution td"))]
                    village_info = map_details.select("table#village_info")[0]
                    tile_info["type"] = "village"
                    tile_info["tribe"] = village_info.select("tr.first td")[0].get_text()
                    tile_info["owner"] = village_info.select("td.player")[0].get_text()
                    tile_info["capital"] = True if soup_tile.select("h1 span.mainVillage") else False
                else:
                    tile_info["type"] = "abandoned valley"
                    tile_info["resource_fields"] = [{
                        "type": resource_field_types[index],
                        "count": int(_.select("td.val")[0].get_text())
                    } for index, _ in enumerate(map_details.select("table#distribution tr")) if _.select("td.val")]
        return tile_info

    def upgrade(self, slot_id, building_id=None, dryrun=False):
        info = self.get_info()
        if not (1 <= slot_id <= 40):
            return False
        build_id = [_ for _ in info["resource_fields" if slot_id < 19 else "buildings"] if _["id"] == slot_id][0]["resource_id" if slot_id < 19 else "building_id"]
        if slot_id < 19 or build_id:  # resource fields or already built up
            action_page = self.session.get("https://{server}{url}".format(
                server=self.server,
                url=self.urls["build"]
            ), params={
                "id": slot_id,
                "gid": build_id
            })
            action_soup = BeautifulSoup(action_page.text, "html.parser")
            action_info = {"demand": {}}
            action_info["slot_id"] = slot_id
            action_info["build_id"] = build_id
            action_demand = action_soup.select("div#contract div.resource")
            action_info["demand"] = {self.mapping["resources_long"][index]: int(_.get_text()) for index, _ in enumerate(action_demand[:len(self.mapping["resources_long"])])}
            action_info["duration"] = action_soup.select("div.duration")[0].get_text()
            action_button = action_soup.select("div.upgradeButtonsContainer button")[0]
            if "green" in action_button.get("class"):
                action_info["url"] = action_button.get("onclick").split("'")[1]
                if not dryrun:
                    self.session.get("https://{server}{url}".format(
                        server=self.server,
                        url=action_info["url"])
                    )
                return {
                    "upgrading": True, 
                    "action_info": action_info, 
                    "message": "ok"
                }
            else:
                return {
                    "upgrading": False, 
                    "action_info": action_info,
                    "message": "upgrade not available"
                }
        else:  # no building at an inner slot
            action_page = self.session.get("https://{server}{url}".format(
                server=self.server,
                url=self.urls["build"]
            ), params={
                "id": slot_id
            })
            action_soup = BeautifulSoup(action_page.text, "html.parser")
            available_building = [{
                "id": int(re.search("\d+", _.select("div.contract")[0].get("id")).group()),
                "name": _.select("h2")[0].get_text().lower()
            } for _ in action_soup.select("div#build div.buildingWrapper") if _.select("button.green")]
            if building_id not in [_["id"] for _ in available_building]:
                return {
                    "upgrading": False, 
                    "available_building": available_building,
                    "message": "building not available"
                }
            else:
                action_info = {"demand": {}}
                action_info["slot_id"] = slot_id
                action_info["build_id"] = building_id
                action_demand = action_soup.select("div#contract_building{building_id} div.resource".format(
                    building_id=building_id    
                ))
                action_info["demand"] = {self.mapping["resources_long"][index]: int(_.get_text()) for index, _ in enumerate(action_demand[:len(self.mapping["resources_long"])])}
                action_info["duration"] = action_soup.select("div.duration")[0].get_text()
                action_button = action_soup.select("div#contract_building{building_id} button.green".format(
                    building_id=building_id    
                ))[0]
                action_info["url"] = action_button.get("onclick").split("'")[1]
                if not dryrun:
                    self.session.get("https://{server}{url}".format(
                        server=self.server,
                        url=action_info["url"])
                    )
                return {
                    "upgrading": True, 
                    "action_info": action_info, 
                    "message": "ok"
                }
