from dotenv import load_dotenv

from workflow import BuildingKnowledgeGraphBuilder
from langchain_openai import ChatOpenAI

load_dotenv()

user_input = """
    RoomR building is composed by 4 classrooms (R1, R1B, R2, R2B). It's total floor area is 450 square meters.
    An Air Handling Unit (AHU_R) feeds all the classrooms.
    Each classroom has a zone air temperature sensor (ZT_R1, ZT_R1B, ZT_R2, ZT_R2B).
    AHU_R is composed by the following equipments: a cooling coil (AHU_R_CC), a supply fan (AHU_R_SF), a return fan (AHU_R_RF), an outside damper (AHU_R_OD) and a return damper (AHU_R_RD).
    Each equipment has the following sensors:
    - The cooling coil has a valve position sensor (AHU_R_CC_VPS)
    - The outdoor air damper has a damper position sensor (AHU_R_OD_DPS)
    - The return air damper has a damper position sensor (AHU_R_RD_DPS)
    - The return fan has a speed setpoint and a speed sensor (AHU_R_RF_SPD_DM, AHU_R_RF_SPD)
    - The supply fan has a speed setpoint and a speed sensor (AHU_R_SF_SPD_DM, AHU_R_SF_SPD)
    The Air Handling Unit is equipped with the following sensors:
    - a supply air temperature sensor (AHU_R_SAT)
    - a return air temperature sensor (AHU_R_RAT)
    - an outside air temperature sensor (AHU_R_OAT)
    - a mixed air temperature sensor (AHU_R_MAT)
    - a supply air temperature setpoint (AHU_R_SAT_SP)
    - an operating mode status (AHU_R_SYS_MODE)
    - a supply air flow sensor (AHU_R_SAF)
    - a return air flow sensor (AHU_R_RAF)
    - and an outside air flow sensor (AHU_R_OAF).
"""

ontology_name = "Brick"
uri = "http://example.com/building#"
max_iterations = 3
user_instructions_entity_extractor = ("When extract entities, go as much in detail as possible when finding the most "
                                      "representative entities. For example, if the user mentioned a supply air "
                                      "temperature sensor, retrieve the Supply_Air_Temperature_Sensor class. Focus also"
                                      "on external references classes to encode the timeseries references.")

user_instructions_relationship_extractor = ("Implement the TimeseriesReference linking each reference to its own sensor "
                                            "by means of https://brickschema.org/schema/Brick/ref#hasExternalReference predicate."
                                            "(example: bldg:AHU_R_SAT ref:hasExternalReference bldg:AHU_R_SAT_Ref"
                                            "bldg:AHU_R_SAT_Ref a ref:TimeseriesReference"
                                            "bldg:AHU_R_SAT_Ref ref:hasTimeseriesId \"AHU_R_SAT\"^^xsd:string).")

llm_instance = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0
)

kg_builder = BuildingKnowledgeGraphBuilder(model=llm_instance, max_iterations=max_iterations)

results = kg_builder.run(
    {
        "user_input": user_input,
        "user_instructions_entity_extractor": user_instructions_entity_extractor,
        "user_instructions_relationship_extractor": user_instructions_relationship_extractor,
        "ontology_name": ontology_name,
        "uri": uri
    }
)

kg = kg_builder.get_final_kg()

print(kg.serialize(format="ttl"))
