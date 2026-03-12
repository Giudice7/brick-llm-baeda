# Brick Schema Overview & Modeling Guidelines

## Ecosystem
Brick is designed to be used in conjunction with other specialized ontologies to provide a comprehensive, multi-dimensional digital twin of a building:
* **REC (RealEstateCore):** Primarily utilized for the architectural, spatial, and topological aspects of a building. It defines how spaces, rooms, and building structures relate to one another.
* **Brick:** Strictly focused on the operational layer, specifically HVAC systems, mechanical and electrical equipment, and their associated telemetry.
* **REF:** Employed to model external references, linking entities in the RDF graph to external databases, timeseries databases, or BIM models.
* **QUDT:** Used to rigorously define the units of measure associated with data points (e.g., mapping a temperature sensor to degrees Celsius).

## Entity Classifications
An Entity is a digital representation of any physical, logical, or virtual item in and around a building. Brick classifies entities into three main flavors:

* **Physical Entities:** Anything that has a physical presence in the world. 
    * *Mechanical Equipment:* Air handling units, variable air volume (VAV) boxes, luminaires, and lighting systems.
    * *Networked Devices:* Electric meters, thermostats, electric vehicle chargers.
    * *Spatial Elements:* Buildings, floors, and rooms (often modeled in tandem with REC).
* **Virtual Entities:** Anything whose representation is based in software. 
    * *Sensing and Status Points:* Allow software to read the current state of the world (e.g., the value of a temperature sensor, the speed of a fan).
    * *Actuation Points:* Allow software to write values (e.g., temperature setpoints or brightness of a lighting fixture).
    * *Computed Points:* Software-calculated metrics, such as average temperatures or electric meter aggregates.
* **Logical Entities:** Entities or collections defined by a set of rules. 
    * *Examples:* HVAC zones and Lighting zones.

Brick usually provides very detailed entity classifications. For instance, Brick define classes such as `brick:Air_Handling_Unit`, `brick:Supply_Air_Temperature_Sensor`, etc.

## Relationship Philosophy
Relationships express how entities interact and are associated with each other. Brick relationships outline several building perspectives:

* **Composition:** What things make up other things. 
    * *Physical composition* describes what equipment can be composed of other equipment (e.g., a VAV made up of a damper, fan, and reheat coil) and how locations are composed of other locations. 
    * *Logical composition* describes how concepts can be broken down (e.g., an HVAC zone consisting of a set of rooms).
* **Topology:** The way in which things are connected or arranged. This includes how equipment is connected sequentially to affect or modulate media (like air or water) as it flows through the building. It also describes spatial adjacencies.
* **Telemetry:** The data sources associated with logical, physical, or virtual things. In BMS parlance, these are called "Points" and consist of the digital representations of the sensors, setpoints, commands, alarms, and parameters that constitute the operational data of a building.