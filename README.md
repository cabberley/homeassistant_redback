# Redback Technologies integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

[Redback Technologies](https://redbacktech.com/) produces a range of inverter and battery systems. This integration uses the 
- Redback Technologies Public API to sync solar and battery energy data.
- Redback Technologies Portal Website to Control your Inverters settings. (This is the portal.redbacktech.com website)

## Enhancements to the original Code by JuiceJuice
- **The Biggest difference is that this version can control your inverter and set it to charge or discharge for a pre determined time!**
- Restructured and renamed the entities to be more aligned and user friendly.
- Uses a newer Redback API version which provides a significant amount of additional data about your PV panels and each battery in your stack
- Added a lot of detail as attributes for information to some sensors.
- reworked a lot of the code and tidied it up removing redundant code.
- Set up some additional data points that I will probably surface when time allows and I get motivated.

## Pre-requisites

You need to contact Redback Technologies support team to request API access. This appears to be available to any customer who asks. You will receive access details including "Client ID" and "Client Secret" which are necessary for this integration.
You will also need your email & Password that you use to access the portal website or mobile app.

## Installation

Install the repository through HACS (**you will need to add this repository as a custom repository, it is different to the one that auto populates the HACS respository**) or by manually copying the `custom_components/redback` folder into your `custom_components` folder.

## Configuration

Once you have installed the component, it should be available for configuration through the user interface.

To setup the integration, got to Configuration -> Integrations, and search for Redback Technologies Portal.

Use the client ID and client secret supplied by Redback support team. 
- Client ID goes in "Redback client ID" field.
- Secret ID goes in "Redback Secret ID" field.
- your email address goes in the "portal email" field.
- Your password goes in the "Portal Password" field.
- You can also give the device a friendly name to suit your needs.

The "Redback Site" field is only required when you have multiple Redback Sites. If you have a single inverter then leave this field alone. For multiple sites, each inverter is a "site", and you simply indicate which inverter you are setting up (first, second, third, etc.)

No further configuration is required. Errors will be reported in the log.

Re-authentication of Redback devices is supported; Home Assistant will notify you when the previously working Redback API credentials expire. In this case, you can choose to re-configure from the integrations page and enter your new Redback API credentials. It is not possible to manually trigger re-authentication, but you can update credentials by hand by editing the `core.config_entries` file in the Home Assistant `.storage` folder (search for "redback" to find the configuration items).

## Usage

The Redback Technologies data source is updated every minute by your inverter. This integration will automatically read the data every minute and update the relevant HA entities, e.g., "Grid Import Total".

## Notes and a vote of thanks!
- Thanks to JuiceJuice for starting the base code. Without his input I wouldn't have gotten around to controlling my Redback to the extent this fork has.
- My site is a single ST10000 Smart Hybrid (Three Phase) Inverter with a full 28.4 kWh of Battery.
- I also use [Amber Energy](https://www.amber.com.au) as my Energy Retailer, paying wholesale rates for FIT, and through using my HA code I haven't paid for electricity on over 18 months!
- If you do sign up to Amber use this [mates link](https://mates.amber.com.au) with my mates code AXF9NT45 and get a $30 discount on signing, I also get $30, which is a nice little reward in appreaciation of liking my HA Integration!

## Notes from JuiceJuice's original Readme worth repeating
- This was developed for the ST10000 Smart Hybrid (three phase) inverter with integrated battery
- This has been tested for the SH5000 Smart Hybrid (single phase) inverter with integrated battery (thanks to "pcal" from HA Community forums)
- This has also been tested for other inverters now, including those without battery (thanks djgoding and LachyGoshi)
- Please file any issues at the Github site
- I have provided sufficient sensor entities to drive the "Energy" dashboard on HA, you just need to configure your dashboard with the relevant "Total" sensors

## TO DO
- The original code worked on the basis that a Redback Site was the Device. It turns out that in HASS terminology, THe Invertors are the Devices, Site is actually a Wrapper, and possibly could consider a HUB in HASS Terminology. To fix this properly in "HASS" world is a bit of work to the core of the code unfortunately. I do have some ideas on how to work around this but it will take time to fix it.
- Try and add "Utility Meters" in the code itself to track Daily, Monthly and Yearly values for the various kWh loads that Redback tracks.
- Considering breaking up this monoloithic "Device" into several types. Site, Inverter & Battery
- While the RedBack controls technically aren't surfacing the "Curtailment" that some people need, I think I found a way to achieve that, needs some time.
