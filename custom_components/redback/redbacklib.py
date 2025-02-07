""" Redback Inverter library, for download of cloud portal data """

import aiohttp
import asyncio
from math import sqrt
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
from json.decoder import JSONDecodeError



class RedbackError(Exception):
    """Redback Inverter general HTTP error"""

class RedbackConnectionError(Exception):
    """Redback Inverter connection error"""

class RedbackAPIError(Exception):
    """Redback Inverter API error"""


class RedbackInverter:
    """Gather Redback Inverter data from the cloud API"""

    serial = None
    siteId = None
    siteIndex = 1
    _apiPrivate = True
    _apiBaseURL = ""
    _apiCookie = ""
    _OAuth2_client_id = ""
    _OAuth2_client_secret = ""
    _OAuth2_bearer_token = ""
    _OAuth2_next_update = datetime.now()
    _apiResponse = "json"
    _inverterInfo = None
    _energyData = None
    _energyDataUpdateInterval = timedelta(minutes=1)
    _energyDataNextUpdate = datetime.now()
    _inverterInfoUpdateInterval = timedelta(minutes=15)
    _inverterInfoNextUpdate = datetime.now()
    _scheduleData = None
    _scheduleDataUpdateInterval = timedelta(minutes=1)
    _scheduleDataNextUpdate = datetime.now()
    _apiPublicRequestMap = {
        "public_BasicData": "EnergyData/With/Nodes",
        "public_StaticData": "EnergyData/{self.siteId}/Static",
        "public_DynamicData": "EnergyData/{self.siteId}/Dynamic?metadata=true",
        "public_ScheduleData": "Schedule/By/Site/{self.siteId}?includeStale=false",
        "public_ConfigData": "Configuration/{self.siteId}/Configuration"
    }
    _ordinalMap = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }

    def __init__(self, auth_id, auth, apimethod, session, site_index=1):
        """Constructor: needs API details (public = OAuth2 client_id and secret, private = auth cookie and inverter serial number)"""
        self._session = session
        self._apiPrivate = (apimethod == 'private') # Public API vs Private API
        if type(site_index) is str:
            self.siteIndex = self._ordinalMap.get(site_index.lower(), 1)
        elif type(site_index) is int:
            self.siteIndex = site_index

        # Private API
        if self._apiPrivate:
            self._apiBaseURL = "https://portal.redbacktech.com/api/v2/"
            self.serial = auth_id
            self._apiSerial = "?SerialNumber=" + self.serial
            self._apiCookie = auth

        # Public API
        else:
            self._apiBaseURL = "https://api.redbacktech.com/Api/v2/"
            self._OAuth2_client_id = auth_id.encode()
            self._OAuth2_client_secret = auth.encode()

    def isPrivateAPI(self):
        return self._apiPrivate

    async def hasBattery(self):
        # Note: private API doesn't have "BatteryCount", need examples without
        # battery so the hasBattery() method can be updated to suit
        inverter_info = await self.getInverterInfo()
        return inverter_info.get("BatteryCount", 0) > 0

    async def _apiGetBearerToken(self):
        """Returns an active OAuth2 bearer token for use with public API methods"""

        # do we need to request a new bearer token?
        if datetime.now() > self._OAuth2_next_update:
            full_url = self._apiBaseURL + 'Auth/token'
            data = b'client_id=' + self._OAuth2_client_id + b'&client_secret=' + self._OAuth2_client_secret
            headers = { "Content-Type": "application/x-www-form-urlencoded" }

            # retry API request if connection error
            retries = 3
            for i in range(retries):
                try:
                    response = await self._session.post(url=full_url, data=data, headers=headers) 

                except aiohttp.ClientConnectorError as e:
                    # retry logic for error "Cannot connect to host api.redbacktech.com:443 ssl:default [Try again]"
                    if i < retries-1:
                        continue
                    else:
                        raise RedbackConnectionError(
                            f"HTTP OAuth2 Connection Error. {e}"
                        ) from e
                except aiohttp.ClientResponseError as e:
                    raise RedbackError(
                        f"HTTP Response Error. {e.code} {e.reason}"
                    ) from e
                except HTTPError as e:
                    # 400 Bad Request = client_id not found
                    # 401 Unauthorized = client_secret incorrect
                    # 404 Not Found = bad endpoint
                    # e.read().decode() returns Unicode string JSON, the "error" key defines the error type (https://www.oauth.com/oauth2-servers/access-tokens/access-token-response/)
                    raise RedbackError(
                        f"HTTP Error. {e.code} {e.reason}"
                    ) from e
                except URLError as e:
                    # If we get here, the URL is wrong or down
                    raise RedbackError(
                        f"URL Error. {e.reason}"
                    ) from e

                break

            # collect data packet
            try:
                data = await response.json()
            except JSONDecodeError as e:
                raise RedbackAPIError(
                    f"JSON Error. {e.msg}. Pos={e.pos} Line={e.lineno} Col={e.colno}"
                ) from e

            # build authorization string
            # (KeyError means the auth was unsuccessful)
            try:
                self._OAuth2_bearer_token = data['token_type'] + ' ' + data['access_token']
            except KeyError as e:
                raise RedbackAPIError(
                    f"OAuth2 Error. {data['error']}: {data['error_description']}"
                )

            # set update timeout
            self._OAuth2_next_update = datetime.now() + timedelta(seconds=int(data['expires_in']))

        return self._OAuth2_bearer_token

    async def _apiRequest(self, endpoint):
        """Call into Redback cloud API"""

        request_headers = {}
        full_url = ""

        # Public API endpoint
        if endpoint.startswith("public_"):
            if not self.siteId and endpoint != "public_BasicData":
                self.siteId = await self.getSiteId()
            full_url = self._apiBaseURL + self._apiPublicRequestMap[endpoint]
            full_url = eval(f"f'{full_url}'") # replace {vars} in full_url
            request_headers = {"authorization": await self._apiGetBearerToken()} 

        # Private API endpoint
        else:
            request_headers = {"Cookie": self._apiCookie} 
            if endpoint == "energyflowd2":
                # https://portal.redbacktech.com/api/v2/energyflowd2/$SERIAL
                full_url = self._apiBaseURL + endpoint + "/" + self.serial
            else:
                # https://portal.redbacktech.com/api/v2/inverterinfo?SerialNumber=$SERIAL
                full_url = self._apiBaseURL + endpoint + self._apiSerial

        # retry API request if connection error
        retries = 3
        for i in range(retries):
            try:
                response = await self._session.get(full_url, headers=request_headers) 

            except aiohttp.ClientConnectorError as e:
                # retry logic for error "Cannot connect to host api.redbacktech.com:443 ssl:default [Try again]"
                if i < retries-1:
                    continue
                else:
                    raise RedbackConnectionError(
                        f"HTTP Connection Error. {e}"
                    ) from e
            except aiohttp.ClientResponseError as e:
                raise RedbackError(
                    f"HTTP Response Error. {e.code} {e.reason}"
                ) from e
            except HTTPError as e:
                raise RedbackError(
                    f"HTTP Error. {e.code} {e.reason}"
                ) from e
            except URLError as e:
                raise RedbackError(f"URL Error. {e.reason}") from e

            break

        # check for API error (e.g. expired credentials or invalid serial)
        if not response.ok:
            message = await response.text()
            raise RedbackAPIError(f"{response.status} {response.reason}. {message}")

        # collect data packet
        try:
            data = await response.json()
        except JSONDecodeError as e:
            raise RedbackAPIError(
                f"JSON Error. {e.msg}. Pos={e.pos} Line={e.lineno} Col={e.colno}"
            ) from e

        return data

    async def testConnection(self):
        """Tests the API connection, will return True or raise RedbackError or RedbackAPIError"""

        if self._apiPrivate:
            testData = await self._apiRequest("inverterinfo")
        else:
            testData = await self._apiRequest("public_BasicData")

        return True

    async def getSiteId(self):
        """Returns site ID via public API"""
        if self.siteId is not None:
            return self.siteId

        index = 0
        siteId = None
        data = await self._apiRequest("public_BasicData")
        for item in data["Data"]:
            if item["Type"] == "Site":
                siteId = item["Id"]
                index += 1
                if index >= self.siteIndex: break
        # return the site ID at desired index, or failing that return the last site ID found
        return siteId

    async def getInverterInfo(self):
        """Returns inverter info (static data, updated first use only)"""

        # we rate-limit the inverter info updates, it is meant to be static data but some values do change
        if datetime.now() > self._inverterInfoNextUpdate or self._inverterInfo == None:
            self._inverterInfoNextUpdate = datetime.now() + self._inverterInfoUpdateInterval

            if self._apiPrivate:
                self._inverterInfo = await self._apiRequest("inverterinfo")
                self._inverterInfo["ModelName"] = self._inverterInfo["Model"]
                self._inverterInfo["FirmwareVersion"] = self._inverterInfo["Firmware"]
                bannerInfo = await self._apiRequest("BannerInfo")
                self._inverterInfo["ProductDisplayname"] = bannerInfo["ProductDisplayname"]
                self._inverterInfo["InstalledPvSizeWatts"] = bannerInfo[
                    "InstalledPvSizeWatts"
                ]
                self._inverterInfo["BatteryCapacityWattHours"] = bannerInfo[
                    "BatteryCapacityWattHours"
                ]

                # Private API keys: Model, Firmware, RossVersion, IsThreePhaseInverter, IsSmartBatteryInverter, IsSinglePhaseInverter, IsGridTieInverter, ProductDisplayname, InstalledPvSizeWatts, BatteryCapacityWattHours

            else:
                dataPacket = (await self._apiRequest("public_StaticData"))["Data"]
                dataConfig = (await self._apiRequest("public_ConfigData"))["Data"]
                staticData = dataPacket["StaticData"]
                nodesData = dataPacket["Nodes"][0]["StaticData"] # assumes node 0 is the inverter, node 1 is usually house load
                self._inverterInfo = staticData["SiteDetails"]
                self._inverterInfo["RemoteAccessConnection.Type"] = staticData["RemoteAccessConnection"]["Type"]
                self._inverterInfo["NMI"] = staticData["NMI"]
                self._inverterInfo["CommissioningDate"] = staticData["CommissioningDate"]
                self._inverterInfo["SiteId"] = staticData["Id"]
                self._inverterInfo["ModelName"] = nodesData["ModelName"]
                self._inverterInfo["BatteryCount"] = nodesData["BatteryCount"]
                self._inverterInfo["BatteryModels"] = ','.join(nodesData["BatteryModels"])
                self._inverterInfo["SoftwareVersion"] = nodesData["SoftwareVersion"]
                self._inverterInfo["FirmwareVersion"] = nodesData["FirmwareVersion"]
                self._inverterInfo["SerialNumber"] = nodesData["Id"]
                self._inverterInfo["Status"] = staticData["Status"]
                self._inverterInfo["BatteryMaxChargePowerW"] = staticData["SiteDetails"]["BatteryMaxChargePowerkW"] * 1000
                self._inverterInfo["BatteryMaxDischargePowerW"] = staticData["SiteDetails"]["BatteryMaxDischargePowerkW"] * 1000
                self._inverterInfo["InverterMaxExportPowerW"] = staticData["SiteDetails"]["InverterMaxExportPowerkW"] * 1000
                self._inverterInfo["InverterMaxImportPowerW"] = staticData["SiteDetails"]["InverterMaxImportPowerkW"] * 1000
                self._inverterInfo["UsableBatteryCapacityOnGridkWh"] = staticData["SiteDetails"]["BatteryCapacitykWh"] * (1-dataConfig["MinSoC0to1"])
                self._inverterInfo["MinSoC0to1"] = dataConfig["MinSoC0to1"]
                self._inverterInfo["MinOffgridSoC0to1"] = dataConfig["MinOffgridSoC0to1"]
                                
                
                
                # Public API keys: BatteryMaxChargePowerkW, BatteryMaxDischargePowerkW, BatteryCapacitykWh, UsableBatteryCapacitykWh, BatteryModels, PanelModel, PanelSizekW, SystemType, InverterMaxExportPowerkW, InverterMaxImportPowerkW, RemoteAccessConnection.Type, NMI, CommissioningDate, ModelName, BatteryCount, SoftwareVersion, FirmwareVersion, SerialNumber

        return self._inverterInfo

    async def getEnergyData(self):
        """Returns energy data (dynamic data, instantaneous with 60s resolution)"""

        # energy data in the cloud data store is only refreshed by the Ouija device every 60s
        if datetime.now() > self._energyDataNextUpdate or self._energyData == None:
            self._energyDataNextUpdate = datetime.now() + self._energyDataUpdateInterval
            if self._apiPrivate:
                self._energyData = (await self._apiRequest("energyflowd2"))["Data"]["Input"]

                # Private API keys: ACLoadW, BackupLoadW, SupportsConnectedPV, PVW, ThirdPartyW, GridStatus, GridNegativeIsImportW, ConfiguredWithBatteries, BatteryNegativeIsChargingW, BatteryStatus, BatterySoC0to100, CtComms

            else:
                self._energyData = (await self._apiRequest("public_DynamicData"))["Data"]
                # gather individual voltage and current per phase
                for phase in self._energyData["Phases"]:
                    self._energyData["VoltageInstantaneousV_" + phase["Id"]] = phase["VoltageInstantaneousV"]
                    self._energyData["CurrentInstantaneousA_" + phase["Id"]] = phase["CurrentInstantaneousA"]
                    self._energyData["PowerFactorInstantaneousMinus1to1_" + phase["Id"]] = phase["PowerFactorInstantaneousMinus1to1"]
                # store an average value too (by calculating total available voltage for three-phase)
                phaseCount = len(self._energyData["Phases"])
                self._energyData["VoltageInstantaneousV"] = round( sum(list(map(lambda x: x["VoltageInstantaneousV"], self._energyData["Phases"]))) / phaseCount * sqrt(phaseCount), 1)
                self._energyData["ActiveExportedPowerInstantaneouskW"] = sum(list(map(lambda x: x["ActiveExportedPowerInstantaneouskW"], self._energyData["Phases"])))
                self._energyData["ActiveImportedPowerInstantaneouskW"] = sum(list(map(lambda x: x["ActiveImportedPowerInstantaneouskW"], self._energyData["Phases"])))
                self._energyData["ActiveNetPowerInstantaneouskW"] = self._energyData["ActiveExportedPowerInstantaneouskW"] - self._energyData["ActiveImportedPowerInstantaneouskW"]
                self._energyData["CurrentInstantaneousA"] = sum(list(map(lambda x: x["CurrentInstantaneousA"], self._energyData["Phases"])))
                self._energyData["InverterMode"] = self._energyData["Inverters"][0]["PowerMode"]["InverterMode"] 
                self._energyData["InverterPowerW"] = self._energyData["Inverters"][0]["PowerMode"]["PowerW"] 
                del self._energyData["TimestampUtc"]
                del self._energyData["SiteId"]
                del self._energyData["Inverters"]
                del self._energyData["Phases"]
                
                # Public API keys: FrequencyInstantaneousHz, BatterySoCInstantaneous0to1, PvPowerInstantaneouskW, InverterTemperatureC, BatteryPowerNegativeIsChargingkW, PvAllTimeEnergykWh, ExportAllTimeEnergykWh, ImportAllTimeEnergykWh, LoadAllTimeEnergykWh, Status, VoltageInstantaneousV, ActiveExportedPowerInstantaneouskW, ActiveImportedPowerInstantaneouskW

        return self._energyData
    

class TestRedbackInverter(RedbackInverter):
    
    """Test class for Redback Inverter integration, returns sample data without any API calls"""

    async def _apiRequest(self, endpoint):
        if endpoint == "inverterinfo":
            return {
                "Model": "ST10000",
                "Firmware": "080819",
                "RossVersion": "2.15.32207.13",
                "IsThreePhaseInverter": True,
                "IsSmartBatteryInverter": False,
                "IsSinglePhaseInverter": False,
                "IsGridTieInverter": False,
            }
        elif endpoint == "BannerInfo":
            return {
                "ProductDisplayname": "Smart Inverter TEST",
                "InstalledPvSizeWatts": 9960.0,
                "BatteryCapacityWattHours": 14200.001,
            }
        elif endpoint == "energyflowd2":
            return {
                "Data": {
                    "Input": {
                        "ACLoadW": 1450.0,
                        "BackupLoadW": 11.0,
                        "SupportsConnectedPV": True,
                        "PVW": 7579.0,
                        "ThirdPartyW": None,
                        "GridStatus": "Export",
                        "GridNegativeIsImportW": 6200.0,
                        "ConfiguredWithBatteries": True,
                        "BatteryNegativeIsChargingW": 0.0,
                        "BatteryStatus": "Idle",
                        "BatterySoC0to100": 98.0,
                        "CtComms": True,
                    }
                }
            }
        elif endpoint == "public_BasicData":
            return {
                "Page": 0,
                "PageSize": 100,
                "PageCount": 1,
                "TotalCount": 1,
                "Data": [
                    {
                        "Id": "S1234123412341",
                        "Nmi": None,
                        "Type": "Site",
                        "Nodes": [
                            {
                                "SerialNumber": "RB12341234123412",
                                "Id": "RB12341234123412",
                                "Nmi": None,
                                "Type": "Inverter",
                                "Nodes": None
                            },
                            {
                                "Id": "Houseload",
                                "Nmi": None,
                                "Type": "Houseload",
                                "Nodes": None
                            }
                        ]
                    }
                ]
            }
        elif endpoint == "public_StaticData":
            return {
                "Data": {
                    "StaticData": {
                        "TimestampUtc": "2022-12-12T06:04:02.0155057Z",
                        "Location": {
                            "Latitude": -27.123,
                            "Longitude": 153.123,
                            "AddressLineOne": "123 Sesame St",
                            "AddressLineTwo": None,
                            "Suburb": "Brisbane",
                            "State": "Qld",
                            "Country": "Australia ",
                            "PostCode": "4000"
                        },
                        "TechnologyProvider": "ABC",
                        "RemoteAccessConnection": {
                            "Type": "ETHERNET",
                            "CustomerChoice": True
                        },
                        "ApprovedCapacityW": None,
                        "SolarRetailer": {
                            "Name": "Retailer Name",
                            "ABN": "81231231231"
                        },
                        "SiteDetails": {
                            "GenerationHardLimitVA": None,
                            "GenerationSoftLimitVA": None,
                            "ExportHardLimitkW": None,
                            "ExportHardLimitW": None,
                            "ExportSoftLimitkW": None,
                            "ExportSoftLimitW": None,
                            "SiteExportLimitkW": None,
                            "BatteryMaxChargePowerkW": 10,
                            "BatteryMaxDischargePowerkW": 10,
                            "BatteryCapacitykWh": 14.22,
                            "UsableBatteryCapacitykWh": 12.798,
                            "PanelModel": " ",
                            "PanelSizekW": 9.96,
                            "SystemType": "Hybrid",
                            "InverterMaxExportPowerkW": 10,
                            "InverterMaxImportPowerkW": 10
                        },
                        "CommissioningDate": "2022-08-18",
                        "NMI": None,
                        "LatestDynamicDataUtc": "2022-12-12T06:03:05Z",
                        "Status": "OK",
                        "Id": "S1234123412341",
                        "Type": "Site",
                        "DynamicDataMetadata": {
                            "ActiveExportedPowerInstantaneouskWMetadata": {
                                "Measured": True
                            },
                            "ActiveImportedPowerInstantaneouskWMetadata": {
                                "Measured": True
                            },
                            "VoltageInstantaneousVMetadata": {
                                "Measured": True
                            },
                            "CurrentInstantaneousAMetadata": {
                                "Measured": True
                            },
                            "PowerFactorInstantaneousMinus1to1Metadata": {
                                "Measured": True
                            },
                            "FrequencyInstantaneousHzMetadata": {
                                "Measured": True
                            },
                            "BatterySoCInstantaneous0to1Metadata": {
                                "Measured": False
                            },
                            "PvPowerInstantaneouskWMetadata": {
                                "Measured": False
                            },
                            "InverterTemperatureCMetadata": {
                                "Measured": True
                            },
                            "BatteryPowerNegativeIsChargingkWMetadata": {
                                "Measured": False
                            },
                            "PvAllTimeEnergykWhMetadata": {
                                "Measured": False
                            },
                            "ExportAllTimeEnergykWhMetadata": {
                                "Measured": True
                            },
                            "ImportAllTimeEnergykWhMetadata": {
                                "Measured": True
                            },
                            "LoadAllTimeEnergykWhMetadata": {
                                "Measured": False
                            }
                        }
                    },
                    "Nodes": [
                        {
                            "StaticData": {
                                "ModelName": "ST10000",
                                "BatteryCount": 4,
                                "SoftwareVersion": "2.16.32211.1",
                                "FirmwareVersion": "080819",
                                "BatteryModels": [
                                    "RB600",
                                    "Unknown",
                                    "Unknown",
                                    "Unknown"
                                    ],
                                "Id": "RB12341234123412",
                                "Type": "Inverter",
                                "DynamicDataMetadata": None
                            },
                            "Nodes": None
                        },
                        {
                            "StaticData": {
                                "Id": "HouseLoad",
                                "Type": "Houseload",
                                "DynamicDataMetadata": None
                            },
                            "Nodes": None
                        }
                    ]
                }
            }
        elif endpoint == "public_DynamicData":
            return {
                "Data": {
                    "TimestampUtc": "2022-12-12T06:08:05Z",
                    "SiteId": "S1234123412341",
                    "Phases": [
                        {
                            "Id": "A",
                            "ActiveExportedPowerInstantaneouskW": 0.33,
                            "ActiveImportedPowerInstantaneouskW": 0,
                            "VoltageInstantaneousV": 233.1,
                            "CurrentInstantaneousA": 1.42,
                            "PowerFactorInstantaneousMinus1to1": 0.79
                        },
                        {
                            "Id": "B",
                            "ActiveExportedPowerInstantaneouskW": 0.347,
                            "ActiveImportedPowerInstantaneouskW": 0,
                            "VoltageInstantaneousV": 235.3,
                            "CurrentInstantaneousA": 1.47,
                            "PowerFactorInstantaneousMinus1to1": 0.785
                        },
                        {
                            "Id": "C",
                            "ActiveExportedPowerInstantaneouskW": 0.422,
                            "ActiveImportedPowerInstantaneouskW": 0,
                            "VoltageInstantaneousV": 236.1,
                            "CurrentInstantaneousA": 1.79,
                            "PowerFactorInstantaneousMinus1to1": 0.829
                        }
                    ],
                    "FrequencyInstantaneousHz": 50.02,
                    "BatterySoCInstantaneous0to1": 0.98,
                    "PvPowerInstantaneouskW": 1.416,
                    "InverterTemperatureC": 45.9,
                    "BatteryPowerNegativeIsChargingkW": 0,
                    "PvAllTimeEnergykWh": 5413.9,
                    "ExportAllTimeEnergykWh": 2612.829,
                    "ImportAllTimeEnergykWh": 175.108,
                    "LoadAllTimeEnergykWh": 3157.7,
                    "Status": "OK",
                    "Inverters": [
                        {
                            "SerialNumber": "RB12341234123412",
                            "PowerMode": {
                                "InverterMode": "Auto",
                                "PowerW": 0
                            }
                        }
                    ]
                },
                "Metadata": {
                    "Latest": "/Api/v2/EnergyData/S1234123412341/Dynamic?metadata=True",
                    "Permalink": "/Api/v2/EnergyData/S1234123412341/Dynamic/At/20221212T060805Z?metadata=True",
                    "Back": {
                        "1m": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221212T060706Z/1?metadata=true",
                        "10m": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221212T055806Z/2?metadata=true",
                        "1h": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221212T050806Z/5?metadata=true",
                        "1d": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221211T060806Z/60?metadata=true",
                        "1w": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221205T060806Z/60?metadata=true"
                    },
                    "Forward": {
                        "1m": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221212T060906Z/1?metadata=true",
                        "10m": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221212T061806Z/2?metadata=true",
                        "1h": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221212T070806Z/5?metadata=true",
                        "1d": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221213T060806Z/60?metadata=true",
                        "1w": "/Api/v2/EnergyData/S1234123412341/Dynamic/LatestBeforeUtc/20221219T060806Z/60?metadata=true"
                    }
                }
            }
        else:
            raise RedbackAPIError(f"TestRedbackInverter: unknown API endpoint {endpoint}")
