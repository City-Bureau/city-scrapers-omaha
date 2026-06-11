from city_scrapers.mixins.oma_sarpy_boc import OmaSarpyBocMixin

spider_configs = [
    {
        "class_name": "OmaSarpyBocBoardMeetings",
        "name": "oma_sarpy_boc_board_meetings",
        "agency": "Sarpy County Board Meetings",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Board Meetings"],
        "name_excludes": ["Board Meetings."],
    },
    {
        "class_name": "OmaSarpyBocBoardOfAdjustment",
        "name": "oma_sarpy_boc_board_of_adjustment",
        "agency": "Sarpy County Board of Adjustment",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Board of Adjustment"],
    },
    {
        "class_name": "OmaSarpyBocBoardOfCorrections",
        "name": "oma_sarpy_boc_board_of_corrections",
        "agency": "Sarpy County Board of Corrections",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Board of Corrections"],
    },
    {
        "class_name": "OmaSarpyBocBoardOfEqualization",
        "name": "oma_sarpy_boc_board_of_equalization",
        "agency": "Sarpy County Board of Equalization",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Board of Equalization"],
    },
    {
        "class_name": "OmaSarpyBocLeasingCorporation",
        "name": "oma_sarpy_boc_leasing_corporation",
        "agency": "Sarpy County Leasing Corporation",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Leasing Corporation"],
    },
    {
        "class_name": "OmaSarpyBocPersonnelPolicyBoard",
        "name": "oma_sarpy_boc_personnel_policy_board",
        "agency": "Sarpy County Personnel Policy Board",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Personnel Policy Board"],
    },
    {
        "class_name": "OmaSarpyBocPlanningCommission",
        "name": "oma_sarpy_boc_planning_commission",
        "agency": "Sarpy County Planning Commission",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Planning Commission"],
    },
    {
        "class_name": "OmaSarpyBocTriCountyRetreat",
        "name": "oma_sarpy_boc_tri_county_retreat",
        "agency": "Sarpy County Tri-County Retreat",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Tri-County Retreat"],
    },
    {
        "class_name": "OmaSarpyBocVeteransServiceCommittee",
        "name": "oma_sarpy_boc_veterans_service_committee",
        "agency": "Sarpy County Veterans Service Committee",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Veterans Service Committee"],
    },
    {
        "class_name": "OmaSarpyBocWastewaterAgency",
        "name": "oma_sarpy_boc_wastewater_agency",
        "agency": "Sarpy County Wastewater Agency",
        "agency_name": "Sarpy County Board of Commissioners",
        "name_prefixes": ["Wastewater Agency"],
    },
]


def create_spiders():
    for config in spider_configs:
        class_name = config["class_name"]
        if class_name not in globals():
            attrs = {k: v for k, v in config.items() if k != "class_name"}
            spider_class = type(OmaSarpyBocMixin)(
                class_name, (OmaSarpyBocMixin,), attrs
            )
            globals()[class_name] = spider_class


create_spiders()
