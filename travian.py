import json
import logging
import os
import re

import requests

from bs4 import BeautifulSoup


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s")


class Travian(object):

    def __init__(self):
        config_file = "config.json"
        try:
            with open(config_file) as f:
                config_json = json.load(f)
        except Exception as e:
            config_json = {}
        self.username = config_json.get("username") or os.getenv("tr_username")
        if not self.username:
            logging.error("Login failed, username is not given.")
            exit()
        self.password = config_json.get("password") or os.getenv("tr_password")
        if not self.password:
            logging.error("Login failed, password is not given.")
            exit()
        self.server = config_json.get("server") or os.getenv("tr_server")
        if not self.server:
            logging.error("Login failed, server is not given.")
            exit()
        self.session = requests.session()
        self.mapping = {
            "resources_short": ["lumber", "clay", "iron", "crop"],
            "resources_long": ["lumber", "clay", "iron", "crop", "free_crop"],
            "resources_overall": ["overall", "lumber", "clay", "iron", "crop"]
        }
        self.urls = {
            "login": "/api/v1/auth/login",
            "dorf1": "/dorf1.php",
            "dorf2": "/dorf2.php",
            "tile": "/api/v1/map/tile-details",
            "build": "/build.php",
            "hero_inventory": "/api/v1/hero/v2/screen/inventory",
            "hero_click": "/api/v1/hero/v2/inventory/click",
            "hero_attributes": "/hero/attributes",
            "hero_appearance": "/hero/appearance",
        }
        self.selectors = {
            "dorf1_player_name": "div#sidebarBoxActiveVillage div.playerName",
            "dorf1_stock": "div#stockBar",
            "dorf1_production": "div.villageInfobox table#production tbody tr",
            "dorf1_resource_fields": "div#resourceFieldContainer a.level",
            "dorf1_troops": "div.villageInfobox table#troops tbody tr",
            "dorf1_movements": "div.villageInfobox table#movements",
            "dorf1_building_list": "div.buildingList ul li",
            "dorf1_village_list": "div#sidebarBoxVillagelist div.villageList div.listEntry",
            "dorf1_loyalty": "div#sidebarBoxActiveVillage div.loyalty span",
            "dorf2_buildings": "div#villageContent div",
        }
        self.producible_buildings = [
            19,  # Barrack
            20,  # Stable
            21,  # Workshop
            25,  # Residence
            26,  # Palace
        ]
        self.logged_in = self.login()

    def login(self):
        logging.debug("Start logging in.")
        nonce_json = self.session.post(f"https://{self.server}{self.urls['login']}", json={
            "name": self.username,
            "password": self.password,
            "w": "1440:900",
            "mobileOptimizations": False
        }).json()
        nonce = nonce_json.get("nonce")
        logging.debug(f"login nonce: {nonce}")
        if nonce:
            token_json = self.session.post(f"https://{self.server}/api/v1/auth/{nonce}").json()
            token = token_json.get("token")
            logging.debug(f"login token: {token}")
            self.token = token
            test_login = self.session.get(f"https://{self.server}{self.urls['dorf1']}")
            soup = BeautifulSoup(test_login.text, "html.parser")
            if soup.select(self.selectors["dorf1_player_name"]) and (soup.select(self.selectors["dorf1_player_name"])[0].string == self.username):
                logging.info(f"Login successfully, username: {self.username}")
                return True
            logging.error("Login failed, cannot get the username.")
        else:
            logging.error("Login failed, cannot get the nonce.")
        return False

    def get_info(self):
        info = {}
        # dorf1
        logging.debug("Getting info from dorf1.")
        dorf1_page = self.session.get(f"https://{self.server}{self.urls['dorf1']}")
        soup_dorf1 = BeautifulSoup(dorf1_page.text, "html.parser")
        logging.debug("Got dorf1 page.")
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
            rf["name"] = self.mapping["resources_overall"][rf["resource_id"]]
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
        info["movements"] = {
            "outgoing": [],
            "incoming": []
        }
        if movements:
            direction = None
            for movement in movements[0].select("tr"):
                if "Incoming" in movement.get_text():
                    direction = "incoming"
                    continue
                if "Outgoing" in movement.get_text():
                    direction = "outgoing"
                    continue
                if direction:
                    info["movements"][direction].append({
                        "type": movement.select("div.mov")[0].get_text().split()[1],
                        "count": int(movement.select("div.mov")[0].get_text().split()[0]),
                        "duration": movement.select("div.dur_r span.timer")[0].get_text()
                    })
        building_list = soup_dorf1.select(self.selectors["dorf1_building_list"])
        info["building_list"] = []
        if building_list:
            for bl in building_list:
                info["building_list"].append({
                    "name": list(bl.select("div.name")[0].strings)[0].strip(),
                    "level": bl.select("div.name span.lvl")[0].get_text(),
                    "duration": bl.select("div.buildDuration span.timer")[0].get_text()
                })
        village_list = soup_dorf1.select(self.selectors["dorf1_village_list"])
        info["village_list"] = [{
            "name": _.select("span.name")[0].get_text(),
            "coordinates": {
                "x": int(_.select("span.coordinatesGrid span.coordinateX")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape').strip("(")),
                "y": int(_.select("span.coordinatesGrid span.coordinateY")[0].get_text().encode('ascii', 'ignore').decode('unicode_escape').strip(")")),
            },
            "current": "active" in _.get("class")
        } for _ in village_list]
        info["loyalty"] = soup_dorf1.select(self.selectors["dorf1_loyalty"])[0].get_text().encode('ascii', 'ignore').decode('unicode_escape')
        culture_points = re.findall('\d+\/\d+', soup_dorf1.select("div.expansionSlotInfo")[0].get("title").encode('ascii', 'ignore').decode('unicode_escape'))[-1]
        info["culture_points"] = {
            "current": int(culture_points.split("/")[0]),
            "next_village": int(culture_points.split("/")[1])
        }
        # dorf2
        logging.debug("Getting info from dorf2.")
        dorf2_page = self.session.get(f"https://{self.server}{self.urls['dorf2']}")
        soup_dorf2 = BeautifulSoup(dorf2_page.text, "html.parser")
        logging.debug("Got dorf2 page.")
        buildings = soup_dorf2.select(self.selectors["dorf2_buildings"])
        info["buildings"] = []
        for building in buildings:
            if building.get("data-aid"):
                b = {
                    "id": int(building.get("data-aid")),
                    "building_id": int(building.get("data-gid")),
                    "name": building.get("data-name"),
                    "level": int(building.select("a")[0]["data-level"]) if building.get("data-name") else 0
                }
            if b not in info["buildings"]:
                info["buildings"].append(b)
        return info

    def get_hero_attributes(self):
        logging.debug("Getting hero info.")
        attributes_page = self.session.get(f"https://{self.server}{self.urls['hero_attributes']}")
        attributes_soup = BeautifulSoup(attributes_page.text, "html.parser")
        logging.debug("Got hero info page.")
        hero_attributes = {}
        hero_attr_raw = json.loads("".join([line for line in attributes_soup.find(text=re.compile(".*screenData.*")).split("\n") if "screenData" in line][0].split(":", 1)[1:]).strip(","))  # too hardcode
        hero_attributes["attribute_points"] = hero_attr_raw["hero"]["attributePoints"]
        hero_attributes["attack_behaviour"] = hero_attr_raw["hero"]["attackBehaviour"]
        hero_attributes["experience"] = hero_attr_raw["hero"]["experience"]
        hero_attributes["experience_percent"] = hero_attr_raw["hero"]["experiencePercent"]
        hero_attributes["health"] = round(hero_attr_raw["hero"]["health"], 2)
        hero_attributes["speed"] = hero_attr_raw["hero"]["speed"]
        hero_attributes["production"] = [{
            "name": _,
            "value": hero_attr_raw["hero"]["productionTypes"][index]
        } for index, _ in enumerate(self.mapping["resources_overall"])]
        return hero_attributes

    def get_hero_inventory(self):
        logging.debug("Getting hero inventory.")
        inventory_raw = self.session.get(f"https://{self.server}{self.urls['hero_inventory']}", headers={
            "Authorization": f"Bearer {self.token}"
        }).json()
        if inventory_raw:
            logging.debug("Got hero inventory JSON.")
        else:
            logging.error("Failed to get hero inventory JSON.")
            return None
        inventory = {}
        inventory["checksum"] = inventory_raw["checksum"]
        inventory["resources"] = {_: {} for _ in self.mapping["resources_short"]}
        for resource in inventory["resources"].keys():
            inventory_resource = [_ for _ in inventory_raw["viewData"]["itemsInventory"] if _["name"] == resource.capitalize()][0]
            inventory["resources"][resource] = {
                "village": inventory_resource["alreadyEquipped"],
                "amount": inventory_resource["amount"],
                "transfer_id": inventory_resource["id"],
                "max_transfer": inventory_resource["maxInput"]
            }
        return inventory

    def get_tile_info(self, x, y):
        logging.debug(f"Getting tile info of ({x}, {y})")
        tile_json = self.session.post(f"https://{self.server}{self.urls['tile']}", json={
            "x": x,
            "y": y
        }, headers={
            "Authorization": f"Bearer {self.token}"
        }).json()
        logging.debug("Got tile info JSON.")
        tile_html = tile_json["html"]
        soup_tile = BeautifulSoup(tile_html, "html.parser")
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
        logging.debug("Execute upgrading job.")
        info = self.get_info()
        if not (1 <= slot_id <= 40):
            logging.error("slot_id should between 1 and 40.")
            return False
        build_id = [_ for _ in info["resource_fields" if slot_id < 19 else "buildings"] if _["id"] == slot_id][0]["resource_id" if slot_id < 19 else "building_id"]
        if slot_id < 19 or build_id:  # resource fields or already built up
            logging.debug(f"slot_id={slot_id}, for resource fields")
            logging.debug("Getting resource field upgrading page.")
            action_page = self.session.get(f"https://{self.server}{self.urls['build']}", params={
                "id": slot_id,
                "gid": build_id
            })
            action_soup = BeautifulSoup(action_page.text, "html.parser")
            logging.debug("Got resource field upgrading page.")
            action_info = {"demand": {}}
            action_info["slot_id"] = slot_id
            action_info["build_id"] = build_id
            action_demand = action_soup.select("div#contract div.resource")
            action_info["demand"] = {self.mapping["resources_long"][index]: int(_.get_text()) for index, _ in enumerate(action_demand[:len(self.mapping["resources_long"])])}
            action_info["duration"] = action_soup.select("div.duration")[0].get_text()
            if action_info["demand"]["lumber"] < info["stock"]["warehouse_capacity"] or action_info["demand"]["clay"] < info["stock"]["warehouse_capacity"] or action_info["demand"]["iron"] < info["stock"]["warehouse_capacity"]:
                logging.warning("Failed to upgrade, warehouse capacity is not enough.")
                return {
                    "upgrading": False,
                    "action_info": action_info,
                    "message": "extend warehouse first"
                }
            if action_info["demand"]["crop"] < info["stock"]["granary_capacity"]:
                logging.warning("Failed to upgrade, granary capacity is not enough.")
                return {
                    "upgrading": False,
                    "action_info": action_info,
                    "message": "extend granary first"
                }
            action_button = action_soup.select("div.upgradeButtonsContainer button")[0]
            if "green" in action_button.get("class"):
                action_info["url"] = action_button.get("onclick").split("'")[1]
                if not dryrun:
                    self.session.get(f"https://{self.server}{action_info["url"]}")
                logging.info(f"Upgrading slot_id={slot_id} now.")
                return {
                    "upgrading": True,
                    "action_info": action_info,
                    "message": "ok"
                }
            else:
                logging.warning("Failed to upgrade, resource is not affordable.")
                return {
                    "upgrading": False,
                    "action_info": action_info,
                    "message": "upgrade not available"
                }
        else:  # no building at an inner slot
            logging.debug(f"slot_id={slot_id}, for inner buildings")
            action_pages = [self.session.get(f"https://{self.server}{self.urls['build']}", params={
                "id": slot_id,
                "category": i
            }) for i in range(1, 4)]
            action_soups = [BeautifulSoup(action_page.text, "html.parser") for action_page in action_pages]
            logging.debug("Got inner building upgrading page.")
            available_buildings = []
            for index, action_soup in enumerate(action_soups):
                available_buildings.extend({
                    "id": int(re.search("\d+", _.select("div.contract")[0].get("id")).group()),
                    "name": _.select("h2")[0].get_text().lower(),
                    "category": index + 1
                } for _ in action_soup.select("div#build div.buildingWrapper") if _.select("button.green"))
            if not building_id:
                logging.warning("Build on an empty slot and building_id is required.")
                return {
                    "upgrading": False,
                    "available_buildings": available_buildings,
                    "message": "the slot is empty, building_id is needed"
                }
            elif building_id not in [_["id"] for _ in available_buildings]:
                logging.warning("This building is not available now.")
                return {
                    "upgrading": False,
                    "available_buildings": available_buildings,
                    "message": "building_id not available"
                }
            else:
                action_info = {"demand": {}}
                action_info["slot_id"] = slot_id
                action_info["build_id"] = building_id
                building_in_category = [_ for _ in available_buildings if _["id"] == building_id][0]["category"]
                action_demand = action_soups[building_in_category - 1].select(f"div#contract_building{building_id} div.resource")
                action_info["demand"] = {self.mapping["resources_long"][index]: int(_.get_text()) for index, _ in enumerate(action_demand[:len(self.mapping["resources_long"])])}
                action_info["duration"] = action_soups[building_in_category - 1].select("div.duration")[0].get_text()
                action_button = action_soups[building_in_category - 1].select(f"div#contract_building{building_id} button.green")[0]
                action_info["url"] = action_button.get("onclick").split("'")[1]
                if not dryrun:
                    self.session.get(f"https://{self.server}{action_info["url"]}")
                logging.info(f"Upgrading slot_id={slot_id} now.")
                return {
                    "upgrading": True,
                    "action_info": action_info,
                    "message": "ok"
                }

    def transfer_resources_from_hero(self, resources):
        for k, v in resources.items():
            hero_inventory = self.get_hero_inventory()
            if v <= hero_inventory["resources"][k]["amount"]:
                if v <= hero_inventory["resources"][k]["max_transfer"]:
                    self.session.post(f"https://{self.server}{self.urls["hero_click"]}", json={
                        "action": "inventory",
                        "checksum": hero_inventory["checksum"],
                        "id": hero_inventory["resources"][k]["transfer_id"],
                        "context": "inventory",
                        "amount": v
                    }, headers={
                        "Authorization": f"Bearer {self.token}"
                    })
                    transferred = self.get_hero_inventory()
                    logging.info(f"Transferred {v} {k} from hero's inventory to the village.")
                    return {
                        "transferred": True,
                        "current_resources": {
                            resource: transferred["resources"][resource]["village"] for resource in transferred["resources"].keys()
                        },
                        "message": "ok"
                    }
                else:
                    logging.warning("Failed, no enough space for warehouse or granary.")
                    return {
                        "transferred": False,
                        "message": "no enough space for warehouse or granary"
                    }
            else:
                logging.warning("Failed, no enough resource in hero's inventory.")
                return {
                    "transferred": False,
                    "message": "no enough resource in hero's invetory"
                }
                
    def get_producible_units(self):
        current_producible_buildings = [_ for _ in self.get_info()["buildings"] if _["building_id"] in self.producible_buildings]
        if not current_producible_buildings:
            logging.warning("No buildings can produce units.")
            return None
        producible_units = []
        for cpb in current_producible_buildings:
            logging.debug(f"Checking producible units in {cpb['name']}(building_id={cpb['building_id']}).")
            building_page = self.session.get(f"https://{self.server}{self.urls['build']}", params={
                "id": cpb["id"],
                "gid": cpb["building_id"]
            })
            building_soup = BeautifulSoup(building_page.text, "html.parser")
            producible_units.extend([{
                "demand": {
                    self.mapping["resources_long"][index]: resource.get_text()
                for index, resource in enumerate(_.select("div.resource"))},
                "duration": _.select("div.duration")[0].get_text(),
                "max_production": int(_.select("a[href='#']")[0].get_text()),
                "troop_type": _.select("input")[0].get("name"),
                "troop_name": _.select("img")[0].get("alt"),
                "building_id": cpb["building_id"]
            } for _ in building_soup.select("div.trainUnits div.troop div.details")])
        return producible_units

    def produce_units(self, product_plan):
        current_producible_buildings = [_ for _ in self.get_info()["buildings"] if _["building_id"] in self.producible_buildings]
        producible_units = self.get_producible_units()
        produce_result = {
            "produced": True,
            "details": []
        }
        #  group by building
        for pb in self.producible_buildings:
            current_building_slot_id = [_["id"] for _ in current_producible_buildings if _["building_id"] == pb][0]
            pb_troop_types = {_["troop_type"]: _ for _ in producible_units if _["building_id"] == pb}
            produce_unit_prefetch_page = self.session.get(f"https://{self.server}{self.urls['build']}", params={
                "id": current_building_slot_id,
                "gid": pb
            })
            prefetch_soup = BeautifulSoup(produce_unit_prefetch_page.text, "html.parser")
            produce_unit_payload = {
                "action": prefetch_soup.select("form[name='snd'] input[name='action']")[0].get("value"),
                "checksum": prefetch_soup.select("form[name='snd'] input[name='checksum']")[0].get("value"),
                "s": int(prefetch_soup.select("form[name='snd'] input[name='s']")[0].get("value")),
                "did": int(prefetch_soup.select("form[name='snd'] input[name='did']")[0].get("value")),
                "s1": prefetch_soup.select("form[name='snd'] button[name='s1']")[0].get("value")
            }
            #  troop types in building
            for ptt in pb_troop_types.keys():
                produce_unit_payload[ptt] = min(int(product_plan.get(ptt, 0)), pb_troop_types[ptt]["max_production"])
            self.session.post(f"https://{self.server}{self.urls['build']}", params={
                "id": current_building_slot_id,
                "gid": pb
            }, json=produce_unit_payload)
            produce_result["details"].append({
                "building_id": current_building_slot_id,
                "detail": produce_unit_payload
            })
        return produce_result
