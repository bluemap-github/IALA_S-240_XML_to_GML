from lxml import etree
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict
import re

def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")

def parse_xml_to_list(path):
    """Parse the XML file and return a list of station dictionaries."""
    xmlTree = etree.parse(path).getroot()
    stations = []

    for tags in xmlTree:
        DGNSSStation = tags
        station = {
            'WKTpos': '',
            'dateOfIssue': '',
            'country': '',
            'dateOfLastUpdate': '',
            'radiobeaconHealth': '',
            'nominalRangeAt': '',
            'referenceStationID': '',
            'nominalRangeKm': '',
            'transmittingStationID': '',
            'transmittedMessageType': '',
            'bitRate': '',
            'signalFrequency': '',
            'stationName': ''
        }
        for content in DGNSSStation:
            station[content.tag] = content.text
        
        # Apply transformations
        station['dateOfIssue'] = format_date(station['dateOfIssue'])
        station['dateOfLastUpdate'] = format_date(station['dateOfLastUpdate'])
        station['WKTpos'] = format_wktpos(station['WKTpos'])
        station['radiobeaconHealth'] = transform_radiobeacon_health(station['radiobeaconHealth'])

        stations.append(station)
    
    return stations

def format_date(date_str):
    """Convert dates from various formats to YYYY-MM-DD."""
    if re.match(r'\d{2}/\d{2}/\d{4}', date_str):
        # Format: DD/MM/YYYY -> YYYY-MM-DD
        return f"{date_str[6:10]}-{date_str[3:5]}-{date_str[0:2]}"
    elif re.match(r'\d{2}/\d{4}', date_str):
        # Format: MM/YYYY -> YYYY-MM-DD (assume day as 01)
        return f"{date_str[3:7]}-{date_str[0:2]}-01"
    elif re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        # Format: YYYY-MM-DD (already correct)
        return date_str
    else:
        # Unknown format, return as is
        return date_str

def format_wktpos(wktpos):
    """Convert POINT (x y) format to x y format."""
    match = re.match(r'POINT \(([-\d\.]+) ([-\d\.]+)\)', wktpos)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return wktpos

def transform_radiobeacon_health(value):
    """Transform radiobeaconHealth values according to the mapping."""
    mapping = {
        "YES": "RadiobeaconOperationNormal",
        "NO": "NoInformationAvailable"
    }
    return mapping.get(value, value)

def create_dgnss_station_almanac_entry(station, index):
    """Create XML element for DgnssStationAlmanac."""
    almanac_elem = ET.Element("DgnssStationAlmanac", attrib={"gml:id": f"DGNSSSTATIONALMANAC-{index:04d}"})

    if station['bitRate']:
        ET.SubElement(almanac_elem, "bitRate").text = station['bitRate']

    if station['signalFrequency']:
        ET.SubElement(almanac_elem, "signalFrequency").text = station['signalFrequency']

    if station['nominalRangeKm']:
        ET.SubElement(almanac_elem, "nominalRangeKm").text = station['nominalRangeKm']

    if station['radiobeaconHealth']:
        ET.SubElement(almanac_elem, "radiobeaconHealth").text = station['radiobeaconHealth']

    if station['referenceStationID']:
        reference_ids = station['referenceStationID'].split(',')
        for ref_id in reference_ids:
            ET.SubElement(almanac_elem, "referenceStationID").text = ref_id.strip()

    if station['stationName']:
        ET.SubElement(almanac_elem, "stationName").text = station['stationName']

    if station['transmittedMessageType']:
        message_types = station['transmittedMessageType'].split(',')
        for msg_type in message_types:
            ET.SubElement(almanac_elem, "transmittedMessageType").text = msg_type.strip()

    if station['transmittingStationID']:
        ET.SubElement(almanac_elem, "transmittingStationID").text = station['transmittingStationID']

    return almanac_elem

def create_radio_station_entry(station, index):
    """Create XML element for RadioStation."""
    radio_elem = ET.Element("RadioStation", attrib={"gml:id": f"RADIOSTATION-{index:04d}"})

    info_elem = ET.SubElement(radio_elem, "informationAssociation", {
        "gml:id": f"ib{index:04d}",
        "xlink:title": "RadioStationToDgnssStationAlmanac",  
        "xlink:href": f"#DGNSSSTATIONALMANAC-{index:04d}"
    })

    geometry_elem = ET.SubElement(radio_elem, "geometry")
    point_property_elem = ET.SubElement(geometry_elem, "S100_pointProperty")
    point_elem = ET.SubElement(point_property_elem, "S100_Point", attrib={"gml:id": f"ID_{index}"})
    pos_elem = ET.SubElement(point_elem, "gml:pos")
    pos_elem.text = station['WKTpos']

    return radio_elem

def create_dgnss_station_region_entry(region_data, index):
    """Create XML element for DgnssStationRegion."""
    region_elem = ET.Element("DgnssStationRegion", attrib={"gml:id": f"DGNSSSTATIONREGION-{index:04d}"})

    for assoc in region_data['associations']:
        ET.SubElement(region_elem, "informationAssociation", {
            "gml:id": f"ia{assoc['id']:04d}",
            "xlink:title": "DgnssStationRegionToDgnssStationAlmanac",  
            "xlink:href": assoc["sharp_almanac_id"]
        })

    ET.SubElement(region_elem, "country").text = region_data['country']
    ET.SubElement(region_elem, "dateOfIssue").text = region_data['dateOfIssue']
    ET.SubElement(region_elem, "dateOfLastUpdate").text = region_data['dateOfLastUpdate']

    return region_elem

def process_dgnss_station_region(stations):
    """Process stations data to create DgnssStationRegion elements."""
    region_data_map = defaultdict(lambda: {
        "country": None,
        "dateOfIssue": None,
        "dateOfLastUpdate": None,
        "associations": []
    })

    for index, station in enumerate(stations, start=1):
        country = station['country']
        if not region_data_map[country]['country']:
            region_data_map[country]['country'] = station['country']
            region_data_map[country]['dateOfIssue'] = station['dateOfIssue']
            region_data_map[country]['dateOfLastUpdate'] = station['dateOfLastUpdate']

        association_data = {
            "id": index,
            "sharp_almanac_id": f"#DGNSSSTATIONALMANAC-{index:04d}"
        }
        region_data_map[country]['associations'].append(association_data)

    # Sort countries alphabetically
    sorted_countries = sorted(region_data_map.keys())

    root = ET.Element("S240:DataSet", attrib={
        "xmlns:S240": "http://www.iho.int/S240/gml/1.0",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:gml": "http://www.opengis.net/gml/3.2",
        "xmlns:S100": "http://www.iho.int/s100gml/1.0",
        "xmlns:s100_profile": "http://www.iho.int/S-100/profile/s100_gmlProfile",
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
        "gml:id": "240DATA"
    })

    for index, country in enumerate(sorted_countries, start=1):
        region_data = region_data_map[country]
        region_entry = create_dgnss_station_region_entry(region_data, index)
        imember = ET.SubElement(root, "imember")
        imember.append(region_entry)

    return root

def process_dgnss_station_almanac(stations):
    """Process stations data to create DgnssStationAlmanac elements."""
    root = ET.Element("S240:DataSet", attrib={
        "xmlns:S240": "http://www.iho.int/S240/gml/1.0",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:gml": "http://www.opengis.net/gml/3.2",
        "xmlns:S100": "http://www.iho.int/s100gml/1.0",
        "xmlns:s100_profile": "http://www.iho.int/S-100/profile/s100_gmlProfile",
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
        "gml:id": "240DATA"
    })

    for index, station in enumerate(stations, start=1):
        almanac_entry = create_dgnss_station_almanac_entry(station, index)
        imember = ET.SubElement(root, "imember")
        imember.append(almanac_entry)

    return root

def process_radio_station(stations):
    """Process stations data to create RadioStation elements."""
    root = ET.Element("members")
    for index, station in enumerate(stations, start=1):
        radio_entry = create_radio_station_entry(station, index)
        root.append(radio_entry)
    return root

def main():
    # Parse XML directly to list of station dictionaries
    path240 = './dgnss_24.xml'
    stations = parse_xml_to_list(path240)

    # Create the root DataSet element with namespaces
    root_gml = ET.Element("S240:DataSet", attrib={
        "xmlns:S240": "http://www.iho.int/S240/gml/1.0",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:gml": "http://www.opengis.net/gml/3.2",
        "xmlns:S100": "http://www.iho.int/s100gml/1.0",
        "xmlns:s100_profile": "http://www.iho.int/S-100/profile/s100_gmlProfile",
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
        "gml:id": "240DATA"
    })

    # Process and append each part in the correct order
    dgnss_station_region_xml = process_dgnss_station_region(stations)
    for member in dgnss_station_region_xml.findall("imember"):
        root_gml.append(member)

    dgnss_station_almanac_xml = process_dgnss_station_almanac(stations)
    for member in dgnss_station_almanac_xml.findall("imember"):
        root_gml.append(member)

    radio_station_xml = process_radio_station(stations)
    root_gml.append(radio_station_xml)

    # Write the final GML to file
    with open("output.gml", "w", encoding="utf-8") as file:
        xml_str = prettify_xml(root_gml)
        file.write(xml_str)

if __name__ == "__main__":
    main()