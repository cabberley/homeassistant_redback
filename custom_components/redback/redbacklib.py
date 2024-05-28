""" Redback Inverter library, for download of cloud portal data """

import aiohttp
import asyncio
from math import sqrt
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
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
    inverterSetPowerW = 0
    inverterSetDurationM = 0
    inverterSetMode = "Auto"
    inverterSetEndTime = datetime.now(timezone.utc) - timedelta(minutes=10)
    inverterResetToAuto = False
    inverterSwVersion = ""
    inverterSerialNumber = ""
    _apiPrivate = True
    _apiBaseURL = "https://api.redbacktech.com/"
    _portalBaseUrl = "https://portal.redbacktech.com/"
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
        "public_Auth": "Api/v2/Auth/token",
        "public_BasicData": "Api/v2/EnergyData/With/Nodes",
        "public_StaticData": "Api/v2/EnergyData/{self.siteId}/Static",
        "public_DynamicData": "Api/v2/EnergyData/{self.siteId}/Dynamic?metadata=true",
        "public_DynamicData_V2.21": "Api/v2.21/EnergyData/{self.siteId}/Dynamic?metadata=false",
        "public_ScheduleData": "Api/v2/Schedule/By/Site/{self.siteId}?includeStale=false",
        "public_ConfigData": "Api/v2/Configuration/{self.siteId}/Configuration"
    }
    _portalRequestMap = {
        "loginUrl": "Account/Login",
        "configureUrl": "productcontrol/Configure?serialNumber=",
        "inverterSetUrl": "productcontrol/Index",
        "accountLogoff": "Account/LogOff/"
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

    def __init__(self, client_id, client_secret, session1, site_index, session2, portalEmail, portalPassword):
        """Constructor: needs API details (public = OAuth2 client_id and secret, private = auth cookie and inverter serial number)"""
        self._session1 = session1
        self._session2 = session2
        self._token = None
        #self._apiPrivate = (apimethod == 'private') # Public API vs Private API
        if type(site_index) is str:
            self.siteIndex = self._ordinalMap.get(site_index.lower(), 1)
        elif type(site_index) is int:
            self.siteIndex = site_index

        self._portalEmail = portalEmail
        self._portalPassword = portalPassword
        self._OAuth2_client_id = client_id.encode()
        self._OAuth2_client_secret = client_secret.encode()


    async def getInverterSetInfo(self, setting):
        if setting == "mode":
            return self.inverterSetMode
        elif setting == "power":
            return self.inverterSetPowerW  
        elif setting == "duration":
            return self.inverterSetDurationM
        elif setting == "end_time":
            return self.inverterSetEndTime

    async def setInverterSetInfo(self, setting, value):
        if setting == "mode":
            self.inverterSetMode = value
        elif setting == "power":
            self.inverterSetPowerW = value
        elif setting == "duration":
            self.inverterSetDurationM = value
        elif setting == "end_time":
            self.inverterSetEndTime = value
        elif setting == "reset":
            self.inverterResetToAuto = False

    async def hasBattery(self):
        inverter_info = await self.getInverterInfo()
        return inverter_info.get("BatteryCount", 0) > 0
    
    async def getPhaseCount(self):
        energy_data_info = await self.getEnergyData()
        return energy_data_info.get("PhaseCount", 0)
    
    async def getPvCount(self):
        energy_data_info = await self.getEnergyData()
        return energy_data_info.get("PvCount", 0)
    
    async def getBatteryCabinetCount(self):
        energy_data_info = await self.getEnergyData()
        return energy_data_info.get("BatteryCabinetCount", 0)
    
    async def getBatteryCount(self):
        energy_data_info = await self.getEnergyData()
        return len(energy_data_info["Battery"]["Modules"])

    async def _apiGetBearerToken(self):
        """Returns an active OAuth2 bearer token for use with public API methods"""

        # do we need to request a new bearer token?
        if datetime.now() > self._OAuth2_next_update:
            fullUrl = self._apiBaseURL + self._apiRequest("public_Auth") #"Api/v2/Auth/token" "public_Auth"
            data = b'client_id=' + self._OAuth2_client_id + b'&client_secret=' + self._OAuth2_client_secret
            headers = { "Content-Type": "application/x-www-form-urlencoded" }

            # retry API request if connection error
            retries = 3
            for i in range(retries):
                try:
                    response = await self._session1.post(url=fullUrl, data=data, headers=headers) 

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
            # Refresh Token @ 50% of expires value
            self._OAuth2_next_update = datetime.now() + timedelta(seconds=int(data['expires_in']) / 2) # Good PRactice is to refresh at 50% of expiry time

        return self._OAuth2_bearer_token

    async def _apiRequest(self, endpoint):
        """Call into Redback cloud API"""

        request_headers = {}
        fullUrl = ""

        # API endpoint
        if not self.siteId and endpoint != "public_BasicData":
            self.siteId = await self.getSiteId()
        fullUrl = self._apiBaseURL + self._apiPublicRequestMap[endpoint]
        fullUrl = eval(f"f'{fullUrl}'") # replace {vars} in fullUrl
        request_headers = {"authorization": await self._apiGetBearerToken()} 

        # retry API request if connection error
        retries = 3
        for i in range(retries):
            try:
                response = await self._session1.get(fullUrl, headers=request_headers) 

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
        await self._apiRequest("public_BasicData")
        await self.testConnectionPortal()
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
            dataPacket = (await self._apiRequest("public_StaticData"))["Data"]
            dataConfig = (await self._apiRequest("public_ConfigData"))["Data"]

            staticData = dataPacket["StaticData"]
            nodesData = dataPacket["Nodes"][0]["StaticData"] # assumes node 0 is the inverter, node 1 is usually house load
            self._inverterInfo = staticData["SiteDetails"]
            self._inverterInfo["LocationLatitude"] = staticData["Location"]["Latitude"]
            self._inverterInfo["LocationLongitude"] = staticData["Location"]["Longitude"]
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
            
            self._inverterInfo["GenerationHardLimitVA"] = staticData["SiteDetails"]["GenerationHardLimitVA"]
            self._inverterInfo["GenerationSoftLimitVA"] = staticData["SiteDetails"]["GenerationSoftLimitVA"]
            self._inverterInfo["ExportHardLimitkW"] = staticData["SiteDetails"]["ExportHardLimitkW"]
            self._inverterInfo["ExportHardLimitW"] = staticData["SiteDetails"]["ExportHardLimitW"]
            self._inverterInfo["ExportSoftLimitkW"] = staticData["SiteDetails"]["ExportSoftLimitkW"]
            self._inverterInfo["ExportSoftLimitW"] = staticData["SiteDetails"]["ExportSoftLimitW"]
            self._inverterInfo["SiteExportLimitkW"] = staticData["SiteDetails"]["SiteExportLimitkW"]
            self._inverterInfo["ApprovedCapacityW"] = staticData["ApprovedCapacityW"]
            self._inverterInfo["CommissioningDate"] = staticData["CommissioningDate"]
            self._inverterInfo["PanelModel"] = staticData["SiteDetails"]["PanelModel"]
            self._inverterInfo["PanelSizekW"] = staticData["SiteDetails"]["PanelSizekW"]
            self._inverterInfo["SystemType"] = staticData["SiteDetails"]["SystemType"]
            self.inverterSwVersion = nodesData["SoftwareVersion"]
            self.inverterSerialNumber = nodesData["Id"]
        return self._inverterInfo

    async def getEnergyData(self):
        """Returns energy data (dynamic data, instantaneous with 60s resolution)"""

        if self.inverterSetEndTime < datetime.now(timezone.utc) and not self.inverterResetToAuto :
            await self.setInverterMode(self.inverterSerialNumber, "Auto", 0, self.inverterSwVersion )
            #self._energyData["InverterResetToAuto"] = True
            self.inverterResetToAuto = True

        self._energyData = (await self._apiRequest("public_DynamicData_V2.21"))["Data"]
        # gather individual voltage and current per phase
        for phase in self._energyData["Phases"]:
            self._energyData["VoltageInstantaneousV_" + phase["Id"]] = phase["VoltageInstantaneousV"]
            self._energyData["CurrentInstantaneousA_" + phase["Id"]] = phase["CurrentInstantaneousA"]
            self._energyData["ActiveExportedPowerInstantaneouskW_" + phase["Id"]] = phase["ActiveExportedPowerInstantaneouskW"]
            self._energyData["ActiveImportedPowerInstantaneouskW_" + phase["Id"]] = phase["ActiveImportedPowerInstantaneouskW"]
            self._energyData["ActiveNetPowerInstantaneouskW_" + phase["Id"]] = phase["ActiveExportedPowerInstantaneouskW"] - phase["ActiveImportedPowerInstantaneouskW"]
            self._energyData["PowerFactorInstantaneousMinus1to1_" + phase["Id"]] = phase["PowerFactorInstantaneousMinus1to1"]
        # store an average value too (by calculating total available voltage for three-phase)
        self._energyData["PhaseCount"] = len(self._energyData["Phases"])
        #phaseCount = self._energyData["PhaseCount"]
        self._energyData["VoltageInstantaneousV"] = round( sum(list(map(lambda x: x["VoltageInstantaneousV"], self._energyData["Phases"]))) / self._energyData["PhaseCount"] * sqrt(self._energyData["PhaseCount"] ), 1)
        self._energyData["ActiveExportedPowerInstantaneouskW"] = sum(list(map(lambda x: x["ActiveExportedPowerInstantaneouskW"], self._energyData["Phases"])))
        self._energyData["ActiveImportedPowerInstantaneouskW"] = sum(list(map(lambda x: x["ActiveImportedPowerInstantaneouskW"], self._energyData["Phases"])))
        self._energyData["ActiveNetPowerInstantaneouskW"] = self._energyData["ActiveExportedPowerInstantaneouskW"] - self._energyData["ActiveImportedPowerInstantaneouskW"]
        self._energyData["CurrentInstantaneousA"] = sum(list(map(lambda x: x["CurrentInstantaneousA"], self._energyData["Phases"])))
        self._energyData["InverterMode"] = self._energyData["Inverters"][0]["PowerMode"]["InverterMode"] 
        self._energyData["InverterPowerW"] = self._energyData["Inverters"][0]["PowerMode"]["PowerW"] 
        batteryCount = 1
        for battery in self._energyData["Battery"]["Modules"]:
            self._energyData["Battery_" + str(batteryCount) + "_SoC0To1"] = battery["SoC0To1"]
            self._energyData["Battery_" + str(batteryCount) + "_VoltageV"] = battery["VoltageV"]
            self._energyData["Battery_" + str(batteryCount) + "_CurrentNegativeIsChargingA"] = battery["CurrentNegativeIsChargingA"]
            self._energyData["Battery_" + str(batteryCount) + "_PowerNegativeIsChargingkW"] = battery["PowerNegativeIsChargingkW"]
            batteryCount += 1
        self._energyData["Battery_Total_CurrentNegativeIsChargingA"] = self._energyData["Battery"]["CurrentNegativeIsChargingA"]
        self._energyData["Battery_Total_VoltageV"] = self._energyData["Battery"]["VoltageV"]
        self._energyData["Battery_Total_VoltageType"] = self._energyData["Battery"]["VoltageType"]
        cabinetCount = 0
        for cabinet in self._energyData["Battery"]["Cabinets"]:
            cabinetCount += 1
            self._energyData["Battery_Cabinet_" + str(cabinetCount) + "_TemperatureC"] = cabinet["TemperatureC"]
            self._energyData["Battery_Cabinet_" + str(cabinetCount) + "_FanState"] = cabinet["FanState"]
        self._energyData["BatteryCabinetCount"] = cabinetCount
        pvCount = 0
        for pv in self._energyData["PVs"]:
            pvCount += 1
            self._energyData["PV_" + str(pvCount) + "_PowerkW"] = pv["PowerkW"]
            self._energyData["PV_" + str(pvCount)  + "_VoltageV"] = pv["VoltageV"]
            self._energyData["PV_" + str(pvCount)  + "_CurrentA"] = pv["CurrentA"]
        self._energyData["PvCount"] = pvCount
        self._energyData["InverterSetEndTime"] = self.inverterSetEndTime
        self._energyData["InverterResetToAuto"] = self.inverterResetToAuto
        self._energyData["SerialNumber"] = self._energyData["Inverters"][0]["SerialNumber"]
        del self._energyData["TimestampUtc"]
        del self._energyData["SiteId"]
        del self._energyData["Inverters"]
        del self._energyData["Phases"]
      
        return self._energyData
 
    async def _getToken(self, response, type):
        soup = BeautifulSoup(response , features="html.parser")
        if type == 1: #LOGINURL:
            form = soup.find("form", class_="login-form")
        else:
            form = soup.find('form', id='GlobalAntiForgeryToken')
        hidden_input = form.find("input", type="hidden")
        self._token = hidden_input.attrs['value']
        return 

    async def _portalRequest(self, url, case, databody=None, headers=None):
        if case == 1: #url == LOGINURL and databody is None:
            redbackResponse = await self._session2.get(url)
            response = await redbackResponse.text()
            await self._getToken(response, 1)   
        elif case == 2: #url == CONFIGUREURL + self._serialNumber: 
            redbackResponse = await self._session2.get(url)
            response = await redbackResponse.text()
            await self._getToken(response, 2)
        elif case == 3: #url == ACCOUNTLOGOFF:
            redbackResponse = await self._session2.get(url, data=databody, headers=headers)
            response = await redbackResponse.text()
        else:
            redbackResponse = await self._session2.post(url, data=databody, headers=headers)
            response = await redbackResponse.text()
        return response, redbackResponse.status
    
    async def testConnectionPortal(self):
        self._serialNumber = ""
        self._session2.cookie_jar.clear()
        fullUrl = self._portalBaseUrl + self._portalRequestMap["loginUrl"]
        await self._portalRequest(url=fullUrl, case=1)
        data={"Email": self._portalEmail, "Password": self._portalPassword,"__RequestVerificationToken": self._token}
        await self._portalRequest(url=fullUrl, databody=data, case=4)
        data={"__RequestVerificationToken": self._token}
        headers={"Referer": "https://portal.redbacktech.com/ui/"}
        fullUrl = self._portalBaseUrl + self._portalRequestMap["accountLogoff"]
        await self._portalRequest(url=fullUrl, case=3 ,databody=data, headers=headers)
        return True #if status == 200 else False
    
    async def setInverterMode(self, serialNumber, inverterMode, inverterPower, swVersion):
        self._serialNumber = serialNumber
        self._inverterMode = inverterMode
        self._inverterPower = inverterPower
        self._swVersion = swVersion
        data = None
        inverterOperationType='Set'
        
        #Connect to portal
        self._session2.cookie_jar.clear()
        fullUrl = self._portalBaseUrl + self._portalRequestMap["loginUrl"]
        await self._portalRequest(url=fullUrl, case=1)
        #login to portal
        data={"Email": self._portalEmail, "Password": self._portalPassword,"__RequestVerificationToken": self._token}
        await self._portalRequest(url=fullUrl, databody=data, case=4)
        #change to Settings page
        fullUrl = self._portalBaseUrl + self._portalRequestMap["configureUrl"] + self._serialNumber
        await self._portalRequest(url=fullUrl, case=2)
        #Send Inverter Mode Change
        headers = {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Referer': fullUrl}
        #updateToken, status = await self._apiRequest(LOGINURL)
        data = {'SerialNumber': self._serialNumber,'AppliedTariffId':'','InverterOperation[Type]':inverterOperationType,'InverterOperation[Mode]':self._inverterMode, 'InverterOperation[PowerInWatts]':self._inverterPower, 'InverterOperation[AppliedTarrifId]':'','ProductModelName': '','RossVersion':self._swVersion,'__RequestVerificationToken':self._token} 
        fullUrl = self._portalBaseUrl + self._portalRequestMap["inverterSetUrl"]
        await self._portalRequest(url=fullUrl, databody=data, headers=headers, case=4)
        data={"__RequestVerificationToken": self._token}
        headers={"Referer": "https://portal.redbacktech.com/ui/"}
        fullUrl = self._portalBaseUrl + self._portalRequestMap["accountLogoff"]
        await self._portalRequest(url=fullUrl, case=3 ,databody=data, headers=headers)
        return
    

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
