from lxml import etree
from typing import Union, List, Dict
import re
from datetime import datetime, timedelta
import json
import os
import requests
from pathlib import Path
import copy

class SPASE():
    """Define the conversion strategy for SPASE (Space Physics Archive Search
    and Extract).

    Attributes:
        file: The path to the metadata file. This should be an XML file in
            SPASE format.
        schema_version: The version of the SPASE schema used in the metadata
            file.
        kwargs: Additional keyword arguments for handling unmappable
            properties. See the Notes section below for details.
    """

    def __init__(self, file: str, **kwargs: dict):
        """Initialize the strategy."""
        file = str(file)  # incase file is a Path object
        if not file.endswith(".xml"):  # file should be XML
            raise ValueError(file + " must be an XML file.")
        self.metadata = etree.parse(file)
        self.file = file
        self.schema_version = get_schema_version(self.metadata)
        self.namespaces = {"spase": "http://www.spase-group.org/data/schema"}
        self.kwargs = kwargs
        self.root = self.metadata.getroot()
        # find element in tree to iterate over
        for elt in self.root.iter(tag=etree.Element):
            if (elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData")
                or elt.tag.endswith("Observatory") or elt.tag.endswith("Instrument")):
                self.desiredRoot = elt
        # if want to see entire xml file as a string
        #print(etree.tostring(self.desiredRoot, pretty_print = True).decode(), end=' ')

    def get_id(self) -> str:
        # Mapping: schema:identifier = hpde.io landing page for the SPASE record
        ResourceID = get_ResourceID(self.metadata, self.namespaces)
        hpdeURL = ResourceID.replace("spase://", "https://hpde.io/")

        return hpdeURL

    def get_name(self) -> str:
        # Mapping: schema:name = spase:ResourceHeader/spase:ResourceName
        desiredTag = self.desiredRoot.tag.split("}")
        SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:ResourceHeader/spase:ResourceName"
        name = self.metadata.findtext(
            SPASE_Location,
            namespaces=self.namespaces,
        )
        return name

    def get_description(self) -> str:
        # Mapping: schema:description = spase:ResourceHeader/spase:Description
        desiredTag = self.desiredRoot.tag.split("}")
        SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:ResourceHeader/spase:Description"
        description = self.metadata.findtext(
            SPASE_Location,
            namespaces=self.namespaces,
        )
        return description

    def get_url(self) -> str:
        # Mapping: schema:url = spase:ResourceHeader/spase:DOI (or https://hpde.io landing page, if no DOI)
        desiredTag = self.desiredRoot.tag.split("}")
        SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:ResourceHeader/spase:DOI"
        url = self.metadata.findtext(
            SPASE_Location,
            namespaces=self.namespaces,
        )
        if url is None:
            url = self.get_id()
        return url

    def get_same_as(self) -> Union[List, None]:
        # Mapping: schema:sameAs = spase:ResourceHeader/spase:PriorID
        same_as = []

        # traverse xml to extract needed info
        for child in self.desiredRoot.iter(tag=etree.Element):
            if child.tag.endswith("PriorID"):
                same_as.append(child.text)
        if same_as == []:
            same_as = None
        elif len(same_as) == 1:
            same_as = same_as[0]
        return same_as

    def get_version(self) -> None:
        version = None
        return version

    # commented out partial code that was put on hold due to licenses being added to SPASE soon
    def get_is_accessible_for_free(self) -> None:
        free = None
        """schema:description: spase:AccessInformation/AccessRights"""
        is_accessible_for_free = None
        # local vars needed
        #access = ""

        # iterate thru to find AccessInfo
        #for child in self.desiredRoot:
        #    if access == "Open":
        #        break
        #    if child.tag.endswith("AccessInformation"):
        #        targetChild = child
                # iterate thru to find AccessRights
        #        for child in targetChild:
        #            if child.tag.endswith("AccessRights"):
        #                access = child.text 
        #if access == "Open":
        #    is_accessible_for_free = True
        #else:
        #    is_accessible_for_free = False
        return is_accessible_for_free

    def get_keywords(self) -> Union[Dict, None]:
        # Mapping: schema:keywords = spase:Keyword AND spase:MeasurementType
        keywords = {}
        keywords["keywords"] = []
        keywords["measurementTypes"] = []

        # traverse xml to extract needed info
        for child in self.desiredRoot.iter(tag=etree.Element):
            if child.tag.endswith("Keyword"):
                keywords["keywords"].append(child.text)
            elif child.tag.endswith("MeasurementType"):
                keywords["measurementTypes"].append(child.text)
        if (keywords["keywords"] == []) and (keywords["measurementTypes"] == []):
            keywords = None
        return keywords

    def get_identifier(self) -> Union[Dict, List[Dict], None]:
        # Mapping: schema:identifier = spase:ResourceHeader/spase:DOI (or https://hpde.io landing page, if no DOI)
        # Each item is: {@id: URL, @type: schema:PropertyValue, propertyID: URI for identifier scheme, value: identifier value, url: URL}
        # Uses identifier scheme URI, provided at: https://schema.org/identifier
        #  OR schema:PropertyValue, provided at: https://schema.org/PropertyValue
        url = self.get_url()
        ID = get_ResourceID(self.metadata, self.namespaces)
        hpdeURL = self.get_id()
        # if SPASE record has a DOI
        if "doi" in url:
            temp = url.split("/")
            value = "doi:" + "/".join(temp[3:])
            identifier = [{"@id": url,
                            "@type" : "PropertyValue",
                            "propertyID": "https://registry.identifiers.org/registry/doi",
                            "value": value,
                            "url": url},
                        {"@id": hpdeURL,
                            "@type": "PropertyValue",
                            "propertyID": "SPASE",
                            "value": ID,
                            "url": hpdeURL}
                        ]
        # if SPASE record only has landing page instead
        else:
            identifier = {"@id": url,
                            "@type": "PropertyValue",
                            "propertyID": "SPASE",
                            "url": url,
                            "value": ID}
        return identifier

    def get_citation(self) -> Union[List[Dict], None]:
        # Mapping: schema:citation = spase:ResourceHeader/spase:InformationURL
        citation = []
        information_url = get_information_url(self.metadata)
        if information_url:
            for each in information_url:
                if "name" in each.keys():
                    if "description" in each.keys():
                        citation.append({"@id": each["url"],
                                            "@type": "CreativeWork",
                                            "name": each["name"],
                                            "url": each["url"],
                                            "description": each["description"]})
                    else:
                        citation.append({"@id": each["url"],
                                            "@type": "CreativeWork",
                                            "name": each["name"],
                                            "url": each["url"]})
                else:
                    citation.append({"@id": each["url"],
                                        "@type": "CreativeWork",
                                        "url": each["url"]})
        else:
            citation = None
        return citation

    def get_variable_measured(self) -> Union[List[Dict], None]:
        # Mapping: schema:variable_measured = spase:Parameters/spase:Name, Description, Units
        # Each object is:
        #   {"@type": schema:PropertyValue, "name": Name, "description": Description, "unitText": Units}
        # Following schema:PropertyValue found at: https://schema.org/PropertyValue
        variable_measured = []
        minVal = ""
        maxVal = ""
        paramDesc = ""
        unitsFound = []
        i = 0

        # traverse xml to extract needed info
        for child in self.desiredRoot.iter(tag=etree.Element):
            if child.tag.endswith("Parameter"):
                targetChild = child
                for child in targetChild:
                    unitsFound.append("")
                    try:
                        if child.tag.endswith("Name"):
                            paramName = child.text
                        elif child.tag.endswith("Description"):
                            paramDesc, sep, after = child.text.partition("\n")
                        elif child.tag.endswith("Units"):
                            unit = child.text
                            unitsFound[i] = unit
                        #elif child.tag.endswith("ValidMin"):
                            #minVal = child.text
                        #elif child.tag.endswith("ValidMax"):
                            #maxVal = child.text
                    except AttributeError as err:
                        continue
                if paramDesc and unitsFound[i]:
                    variable_measured.append({"@type": "PropertyValue", 
                                            "name": f"{paramName}",
                                            "description": f"{paramDesc}",
                                            "unitText": f"{unitsFound[i]}"})
                elif paramDesc:
                    variable_measured.append({"@type": "PropertyValue", 
                                        "name": f"{paramName}",
                                        "description": f"{paramDesc}"})
                elif unitsFound[i]:
                    variable_measured.append({"@type": "PropertyValue", 
                                        "name": f"{paramName}",
                                        "unitText": f"{unitsFound[i]}"})
                else:
                    variable_measured.append({"@type": "PropertyValue", 
                                        "name": f"{paramName}"})
                                        #"minValue": f"{minVal}",
                                        #"maxValue": f"{maxVal}"})
                i += 1
        if len(variable_measured) == 0:
            variable_measured = None
        return variable_measured

    def get_included_in_data_catalog(self) -> None:
        included_in_data_catalog = None
        return included_in_data_catalog

    def get_subject_of(self) -> Union[Dict, None]:
        # Mapping: schema:subjectOf = {http://www.w3.org/2001/XMLSchema-instance}MetadataRights
        #   AND spase:ResourceHeader/spase:ReleaseDate
        # Following type:DataDownload found at: https://schema.org/DataDownload
        date_modified = self.get_date_modified()
        metadata_license = get_metadata_license(self.metadata)
        content_url = self.get_id()
        doi = False
        if "doi" in content_url:
            doi = True
            resource_id = get_ResourceID(self.metadata, self.namespaces)
            content_url = resource_id.replace("spase://", "https://hpde.io/")
        # small lookup table for commonly used licenses in SPASE
        #   (CC0 for NASA, CC-BY-NC-3.0 for ESA, etc)
        common_licenses = [
            {
                "fullName": "Creative Commons Zero v1.0 Universal",
                "identifier": "CC0-1.0",
                "url": "https://spdx.org/licenses/CC0-1.0.html",
            },
            {
                "fullName": "Creative Commons Attribution Non Commercial 3.0 Unported",
                "identifier": "CC-BY-NC-3.0",
                "url": "https://spdx.org/licenses/CC-BY-NC-3.0.html",
            },
            {
                "fullName": "Creative Commons Attribution 1.0 Generic",
                "identifier": "CC-BY-1.0",
                "url": "https://spdx.org/licenses/CC-BY-1.0.html",
            },
        ]

        if content_url:
            # basic format for item
            entry = {
                "@type": "DataDownload",
                "name": "SPASE metadata for dataset",
                "description": "The SPASE metadata describing the indicated dataset.",
                "encodingFormat": "application/xml",
                "contentUrl": content_url,
                "identifier": content_url,
            }
            # if hpde.io landing page not used as top-level @id, include here as @id
            if doi:
                entry["@id"] = content_url
            if metadata_license:
                # find URL associated w license found in top-level SPASE line
                license_url = ""
                for entry in common_licenses:
                    if entry["fullName"] == metadata_license:
                        license_url = entry["url"]
                # if license is not in lookup table
                if not license_url:
                    # find license info from SPDX data file at
                    #   https://github.com/spdx/license-list-data/tree/main
                    #   and add to common_licenses dictionary OR provide the
                    #   fullName, identifier, and URL (in that order) as arguments
                    #   to the conversion function. Then rerun script for those that failed.
                    pass
                else:
                    entry["license"] = license_url

                # if date modified is available, add it
                if date_modified:
                    entry["dateModified"] = date_modified

            subject_of = entry
        else:
            subject_of = None
        return subject_of

    def get_distribution(self) -> Union[List[Dict], None]:
        # Mapping: schema:distribution = /spase:AccessInformation/spase:AccessURL/spase:URL
        #   (if URL is a direct link to download data)
        # AND /spase:AccessInformation/spase:Format
        # Each object is:
        #   {"@type": schema:DataDownload, "contentURL": URL, "encodingFormat": Format}
        # Following schema:DataDownload found at: https://schema.org/DataDownload
        distribution = []
        dataDownloads, potentialActions = get_accessURLs(self.metadata)
        for k, v in dataDownloads.items():
            distribution.append({"@type": "DataDownload",
                                "contentUrl": f"{k}",
                                "encodingFormat": f"{v[0]}"})
        if len(distribution) != 0:
            if len(distribution) == 1:
                distribution = distribution[0]
        else:
            distribution = None
        return distribution

    def get_potential_action(self) -> Union[List[Dict], None]:
        # Mapping: schema:potentialAction = /spase:AccessInformation/spase:AccessURL/spase:URL
        #   (if URL is not a direct link to download data)
        # AND /spase:AccessInformation/spase:Format
        # Following schema:potentialAction found at: https://schema.org/potentialAction
        potential_actionList = []
        startSent = ""
        endSent = ""
        dataDownloads, potentialActions = get_accessURLs(self.metadata)
        temp_covg = self.get_temporal_coverage()
        if temp_covg is not None:
            if type(temp_covg) == str:
                start, sep, end = temp_covg.partition("/")
            else:
                start, sep, end = temp_covg["temporalCoverage"].partition("/")
            # create test end time
            date, sep, time = start.partition("T")
            time = time.replace("Z", "")
            if "." in time:
                time, sep, ms = time.partition(".")
            dt_string = date + " " + time
            dt_obj = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
            # make test stop time 1 minute after start time
            testEnd = dt_obj + timedelta(minutes=1)
            testEnd = str(testEnd).replace(" ", "T")
            # set testEnd as end time if no end time found in record
            if end == "" or end == "..":
                end = testEnd
            else:
                endSent = f"Data is available up to {end}. "
            endSent += f"Use {testEnd} as a test end value."
            startSent = f"Use {start} as default value."

        # loop thru all AccessURLs
        for k, v in potentialActions.items():
            prodKeys = v[1]
            encoding = v[0]
            pattern = "(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(.[0-9]+)?(Z)?"

            # if link has no prodKey
            if prodKeys == "None":
                # if ftp link, do not include @id
                if "ftp" in k: 
                    potential_actionList.append({"@type": "SearchAction",
                                                "target": {"@type": "EntryPoint",
                                                            "contentType": f"{encoding}",
                                                            "url": f"{k}",
                                                            "description": f"Download dataset data as {encoding} file at this URL"}
                                                })
                else:
                    potential_actionList.append({"@type": "SearchAction",
                                            "target": {"@id": f"{k}",
                                                        "@type": "EntryPoint",
                                                        "contentType": f"{encoding}",
                                                        "url": f"{k}",
                                                        "description": f"Download dataset data as {encoding} file at this URL"}
                                            })
            else:
                # loop thru all product keys if there are multiple
                for prodKey in prodKeys:
                    prodKey = prodKey.replace("\"", "")
                    # if link is a hapi link, provide the hapi interface web service to download data
                    if "/hapi" in k:
                        # if ftp link, do not include @id
                        if 'ftp' in k:
                            potential_actionList.append({"@type": "SearchAction",
                                                "target": {"@type": "EntryPoint",
                                                            "contentType": f"{encoding}",
                                                            "urlTemplate": f"{k}/data?id={prodKey}&time.min=(start)&time.max=(end)",
                                                            "description": "Download dataset labeled by id in CSV format based on the requested start and end dates",
                                                            "httpMethod": "GET"},
                                                "query-input": [
                                                    {"@type": "PropertyValueSpecification",
                                                    "valueName": "start",
                                                    "description": f"A UTC ISO DateTime. {startSent}",
                                                    "valueRequired": False,
                                                    "valuePattern": f"{pattern}"},
                                                    {"@type": "PropertyValueSpecification",
                                                    "valueName": "end",
                                                    "description": f"A UTC ISO DateTime. {endSent}",
                                                    "valueRequired": False,
                                                    "valuePattern": f"{pattern}"}
                                                ]
                            })
                        else:
                            potential_actionList.append({"@type": "SearchAction",
                                            "target": {"@id": f"{k}",
                                                        "@type": "EntryPoint",
                                                        "contentType": f"{encoding}",
                                                        "urlTemplate": f"{k}/data?id={prodKey}&time.min=(start)&time.max=(end)",
                                                        "description": "Download dataset labeled by id in CSV format based on the requested start and end dates",
                                                        "httpMethod": "GET"},
                                            "query-input": [
                                                {"@type": "PropertyValueSpecification",
                                                "valueName": "start",
                                                "description": f"A UTC ISO DateTime. {startSent}",
                                                "valueRequired": False,
                                                "valuePattern": f"{pattern}"},
                                                {"@type": "PropertyValueSpecification",
                                                "valueName": "end",
                                                "description": f"A UTC ISO DateTime. {endSent}",
                                                "valueRequired": False,
                                                "valuePattern": f"{pattern}"}
                                            ]
                        })
                    # use GSFC CDAWeb portal to download CDF
                    else:
                        # if ftp link, do not include @id
                        if 'ftp' in k:
                            potential_actionList.append({"@type": "SearchAction",
                                                    "target": {"@type": "EntryPoint",
                                                                "contentType": f"{encoding}",
                                                                "url": f"{k}",
                                                                "description": "Download dataset data as CDF or CSV file at this URL"}
                                                    })
                        else:
                            potential_actionList.append({"@type": "SearchAction",
                                                "target": {"@id": f"{k}",
                                                            "@type": "EntryPoint",
                                                            "contentType": f"{encoding}",
                                                            "url": f"{k}",
                                                            "description": "Download dataset data as CDF or CSV file at this URL"}
                                                })
        if len(potential_actionList) != 0:
            potential_action = potential_actionList
        else:
            potential_action = None
        return potential_action

    def get_date_created(self) -> Union[str, None]:
        # Mapping: schema:dateCreated = spase:ResourceHeader/spase:PublicationInfo/spase:PublicationDate
        # OR spase:ResourceHeader/spase:RevisionHistory/spase:ReleaseDate
        # Using schema:DateTime as defined in: https://schema.org/DateTime
        date_created = self.get_date_published()

        #release, revisions = get_dates(self.metadata)
        #if revisions == []:
            #date_created = str(release).replace(" ", "T")
        # find earliest date in revision history
        #else:
            #print("RevisionHistory found!")
            #date_created = str(revisions[0])
            #if len(revisions) > 1:
                #for i in range(1, len(revisions)):
                    #if (revisions[i] < revisions[i-1]):
                        #date_created = str(revisions[i])
            #date_created = date_created.replace(" ", "T")
        return date_created

    def get_date_modified(self) -> Union[str, None]:
        # Mapping: schema:dateModified = spase:ResourceHeader/spase:ReleaseDate
        # Using schema:DateTime as defined in: https://schema.org/DateTime
        #trigger = False
        release, revisions = get_dates(self.metadata)
        date_modified = str(release).replace(" ", "T")
        #date_created = date_modified
        # confirm that ReleaseDate is the latest date in the record
        #if revisions != []:
            #print("RevisionHistory found!")
            # find latest date in revision history
            #date_created = str(revisions[0])
            #if len(revisions) > 1:
                #for i in range(1, len(revisions)):
                    #if (revisions[i] > revisions[i-1]):
                        #date_created = str(revisions[i])
            #print(date_created)
            #print(date_modified)
            # raise Error if releaseDate is not the latest in RevisionHistory
            #if datetime.strptime(date_created, "%Y-%m-%d %H:%M:%S") != release:
                #raise ValueError("ReleaseDate is not the latest date in the record!")
                #trigger = True
        return date_modified

    def get_date_published(self) -> Union[str, None]:
        # Mapping: schema:datePublished = spase:ResourceHeader/spase:PublicationInfo/spase:PublicationDate
        # OR spase:ResourceHeader/spase:RevisionHistory/spase:ReleaseDate
        # Using schema:DateTime as defined in: https://schema.org/DateTime        
        author, authorRole, pubDate, publisher, dataset, backups, contactsList = get_authors(self.metadata)
        date_published = None
        release, revisions = get_dates(self.metadata)
        if pubDate == "":
            if revisions:
                # find earliest date in revision history
                date_published = str(revisions[0])
                if len(revisions) > 1:
                    for i in range(1, len(revisions)):
                        if (revisions[i] < revisions[i-1]):
                            date_published = str(revisions[i])
                date_published = date_published.replace(" ", "T")
                date_published = date_published.replace("Z", "")
        else:
            date_published = pubDate.replace(" ", "T")
            date_published = date_published.replace("Z", "")
        return date_published

    def get_expires(self) -> None:
        expires = None
        return expires

    def get_temporal_coverage(self) -> Union[str, Dict, None]:
        # Mapping: schema:temporal_coverage = spase:TemporalDescription/spase:TimeSpan/*
        # Each object is:
        #   {temporalCoverage: StartDate and StopDate|RelativeStopDate}
        # Result is either schema:Text or schema:DateTime, found at https://schema.org/Text and https://schema.org/DateTime
        # Using format as defined in: https://github.com/ESIPFed/science-on-schema.org/blob/main/guides/Dataset.md#temporal-coverage
        desiredTag = self.desiredRoot.tag.split("}")
        SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:TemporalDescription/spase:TimeSpan/spase:StartDate"
        start = self.metadata.findtext(
            SPASE_Location,
            namespaces=self.namespaces,
        )
        SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:TemporalDescription/spase:TimeSpan/spase:StopDate"
        stop = self.metadata.findtext(
            SPASE_Location,
            namespaces=self.namespaces,
        )

        if start:
            if stop:
                temporal_coverage = {"@type": "DateTime",
                                    "temporalCoverage": f"{start.strip()}/{stop.strip()}"}
            else:
                temporal_coverage = f"{start}/.."
        else:
            temporal_coverage = None
        return temporal_coverage

    def get_spatial_coverage(self) -> Union[List[Dict], None]:
        # Mapping: schema:spatial_coverage = list of spase:NumericalData/spase:ObservedRegion
        spatial_coverage = []
        desired_tag = self.desiredRoot.tag.split("}")
        spase_location = ".//spase:" + f"{desired_tag[1]}/spase:ObservedRegion"
        all_regions = self.metadata.findall(spase_location, namespaces=self.namespaces)
        for item in all_regions:
            # Split string on '.'
            pretty_name = item.text.replace(".", " ")

            # most basic entry for spatialCoverage
            entry = {
                "@type": "Place",
                "keywords": {
                    "@type": "DefinedTerm",
                    "inDefinedTermSet": {
                        "@id": "https://spase-group.org/data/"
                        + "model/spase-latest/spase-latest_xsd.htm#Region"
                    },
                    "termCode": item.text,
                },
                "name": pretty_name,
            }

            # if this is the first item added, add additional info for DefinedTermSet
            if all_regions.index(item) == 0:
                entry["keywords"]["inDefinedTermSet"]["@type"] = "DefinedTermSet"
                entry["keywords"]["inDefinedTermSet"]["name"] = "SPASE Region"
                entry["keywords"]["inDefinedTermSet"]["url"] = (
                    "https://spase-group.org/data/model/spase-latest"
                    "/spase-latest_xsd.htm#Region"
                )
            spatial_coverage.append(entry)

        if len(spatial_coverage) == 0:
            spatial_coverage = None
        return spatial_coverage

    def get_creator(self) -> Union[List[Dict], None]:
        # Mapping: schema:creator = spase:ResourceHeader/spase:PublicationInfo/spase:Authors
        # OR schema:creator = spase:ResourceHeader/spase:Contact/spase:PersonID
        # Each item is:
        #   {@type: Role, roleName: Contact Role, creator:
        #   {@type: Person, name: Author Name, givenName:
        #   First Name, familyName: Last Name}}
        #   plus the additional properties if available: affiliation and identifier (ORCiD ID),
        #       which are pulled from SMWG Person SPASE records
        # Using schema:Creator as defined in: https://schema.org/creator
        (
            author,
            author_role,
            *_,
            contacts_list,
        ) = get_authors(self.metadata)
        author_str = str(author).replace("[", "").replace("]", "")
        creator = []
        multiple = False
        matching_contact = False
        if author:
            # if creators were found in Contact/PersonID
            if "Person/" in author_str:
                # if multiple found, split them and iterate thru one by one
                if "'," in author_str:
                    multiple = True
                for person in author:
                    if multiple:
                        # keep track of position so roles will match
                        index = author.index(person)
                    else:
                        index = 0
                    # split text from Contact into properly formatted name fields
                    author_str, given_name, family_name = name_splitter(person)
                    # get additional info if any
                    orcid_id, affiliation, ror = get_ORCiD_and_Affiliation(
                        person
                    )
                    # create the dictionary entry for that person and append to list
                    creator_entry = person_format(
                        "creator",
                        author_role[index],
                        author_str,
                        given_name,
                        family_name,
                        affiliation,
                        orcid_id,
                        ror
                    )
                    creator.append(creator_entry)
            # if creators were found in PublicationInfo/Authors
            else:
                # if there are multiple authors
                if len(author) > 1:
                    # get rid of extra quotations
                    for num, each in enumerate(author):
                        if "'" in each:
                            author[num] = each.replace("'", "")
                    # iterate over each person in author string
                    for person in author:
                        matching_contact = False
                        index = author.index(person)
                        family_name, _, given_name = person.partition(", ")
                        # find matching person in contacts, if any, to retrieve
                        #   affiliation and ORCiD
                        for key, val in contacts_list.items():
                            if (not matching_contact) and (person == val):
                                matching_contact = True
                                orcid_id, affiliation, ror = (
                                    get_ORCiD_and_Affiliation(key)
                                    )
                                creator_entry = person_format(
                                    "creator",
                                    author_role[index],
                                    person,
                                    given_name,
                                    family_name,
                                    affiliation,
                                    orcid_id,
                                    ror,
                                )
                        if not matching_contact:
                            creator_entry = person_format(
                                "creator",
                                author_role[index],
                                person,
                                given_name,
                                family_name,
                            )
                        creator.append(creator_entry)
                # if there is only one author listed
                else:
                    # get rid of extra quotations
                    person = author_str.replace('"', "")
                    person = author_str.replace("'", "")
                    if ", " in person:
                        family_name, _, given_name = person.partition(",")
                        # find matching person in contacts, if any, to retrieve affiliation and ORCiD
                        for key, val in contacts_list.items():
                            if not matching_contact:
                                if person == val:
                                    matching_contact = True
                                    orcid_id, affiliation, ror = get_ORCiD_and_Affiliation(
                                        key)
                                    creator_entry = person_format(
                                        "creator",
                                        author_role[0],
                                        person,
                                        given_name,
                                        family_name,
                                        affiliation,
                                        orcid_id,
                                        ror,
                                    )
                        if not matching_contact:
                            creator_entry = person_format(
                                "creator", author_role[0], person, given_name, family_name
                            )
                        creator.append(creator_entry)
                    # no comma = organization = no givenName and familyName
                    else:
                        creator_entry = person_format(
                                "creator", author_role[0], person, "", ""
                            )
                        creator.append(creator_entry)
        # preserve order of elements
        if len(creator) == 0:
            creator = None
        return creator

    def get_contributor(self) -> tuple:
        # Mapping: schema:contributor = spase:ResourceHeader/spase:Contact/spase:PersonID
        # Each item is:
        #   {@type: Role, roleName: Contributor or curator role, contributor: {@type: Person, name: Author Name, givenName: First Name, familyName: Last Name}}
        #   plus the additional properties if available: affiliation and identifier (ORCiD ID),
        #       which are pulled from SMWG Person SPASE records and ROR API
        # Using schema:Person as defined in: https://schema.org/Person
        author, authorRole, pubDate, pub, dataset, backups, contactsList = get_authors(self.metadata)
        contributor = []
        ror = None
        first_contrib = True
        DC_Roles = {}
        role = "ProjectLeader"
        # contributor prioritization (descending)
        DC_Roles["ContactPerson"] = ["GeneralContact", "HostContact", "MetadataContact", "TechnicalContact"]
        DC_Roles["DataCurator"] = ["ArchiveSpecialist"]
        DC_Roles["ProjectLeader"] = ["TeamLeader"]
        DC_Roles["ProjectManager"] = ["InstrumentLead", "MissionManager", "ProgramManager", "ProjectManager"]
        DC_Roles["DataCollector"] = ["DataProducer"]
        DC_Roles["ProjectMember"] = ["Contributor", "Developer", "InstrumentScientist", "ProgramScientist",
                            "ProjectEngineer", "ProjectScientist", "Scientist", "TeamMember"]

        # Step 1: check for ppl w author roles that were not found in PubInfo
        for key, val in contactsList.items():
            if contributor:
                first_contrib = False
            # why .? (not all names will have a period?) Is this even needed?
            if "." not in val:
                # add call to get ORCiD and affiliation
                contributorStr, givenName, familyName = name_splitter(key)
                orcidID, affiliation, ror = get_ORCiD_and_Affiliation(key)
                #if ror == "":
                    #ror = get_ROR(affiliation)
                # if person has more than one author role
                if len(contactsList[key]) > 1:
                    if "CoInvestigator" in contactsList[key]:
                        role = "ProjectMember"
                    individual = person_format("contributor",
                        role,
                        contributorStr,
                        givenName,
                        familyName,
                        affiliation,
                        orcidID,
                        ror,
                        first_contrib)
                else:
                    if contactsList[key][0] == "CoInvestigator":
                        role = "ProjectMember"
                    individual = person_format("contributor",
                        role,
                        contributorStr,
                        givenName,
                        familyName,
                        affiliation,
                        orcidID,
                        ror,
                        first_contrib)
                contributor.append(individual)

        # Step 2: check for ContactPerson, DataCurator, ProjectLeader, ProjectManager,
        #   DataCollector, and ProjectMember roles
        if backups:
            contributor = add_contributors(contributor, backups, DC_Roles)
        # no valid contributors found
        if len(contributor) == 0:
            contributor = None

        return contributor

    def get_provider(self) -> None:
        provider = None
        return provider

    def get_publisher(self) -> Union[Dict, None]:
        # Mapping: schema:publisher = spase:ResourceHeader/spase:Contacts
        # OR spase:ResourceHeader/spase:PublicationInfo/spase:PublishedBy
        # OR spase:AccessInformation/spase:RepositoryID
        # Each item is:
        #   {@type: Organization, name: PublishedBy OR Contact (if Role = Publisher) OR last part of RepositoryID}
        # Using schema:Organization as defined in: https://schema.org/Organization
        author, authorRole, pubDate, publisher, dataset, backups, contactsList = get_authors(self.metadata)
        ror = None
        
        """if publisher == "":
            RepoID = get_repoID(self.metadata)
            (before, sep, publisher) = RepoID.partition("Repository/")
        if ("SDAC" in publisher) or ("Solar Data Analysis Center" in publisher):
            publisher = {"publisherIdentifier": "https://ror.org/04rvfc379",
                        "publisherIdentifierScheme":"ROR",
                        "schemeUri": "https://ror.org/",
                        "name": publisher}
        elif ("SPDF" in publisher) or ("Space Physics Data Facility" in publisher):
            publisher = {"publisherIdentifier": "https://ror.org/00ryjtt64",
                        "publisherIdentifierScheme":"ROR",
                        "schemeUri": "https://ror.org/",
                        "name": publisher}
        else:
            #ror = get_ROR(publisher)
            if ror:
                publisher = {"publisherIdentifier": ror,
                            "publisherIdentifierScheme":"ROR",
                            "schemeUri": "https://ror.org/",
                            "name": publisher}
            else:"""
        if publisher:
            publisher = {"name": publisher}
        return publisher

    def get_funding(self) -> Union[List[Dict], None]:
        # Mapping: schema:funding = spase:ResourceHeader/spase:Funding/spase:Agency 
        # AND spase:ResourceHeader/spase:Funding/spase:Project
        # AND spase:ResourceHeader/spase:Funding/spase:AwardNumber
        # Each item is:
        #   {@type: MonetaryGrant, funder: {@type: Organization, name: Agency}, identifier: AwardNumber, name: Project}
        # Using schema:MonetaryGrant as defined in: https://schema.org/MonetaryGrant
        funding = []
        agency = []
        project = []
        award = []
        ror = None
        # iterate thru to find all info related to funding
        for child in self.desiredRoot.iter(tag=etree.Element):
            if child.tag.endswith("Funding"):
                targetChild = child
                for child in targetChild:
                    if child.tag.endswith("Agency"):
                        agency.append(child.text)
                    elif child.tag.endswith("Project"):
                        project.append(child.text)
                    elif child.tag.endswith("AwardNumber"):
                        award.append(child.text)
        # if funding info was found
        if agency:
            i = 0
            #ror = get_ROR(agency)
            for funder in agency:
                if award and ror:
                    funding.append({"@type": "MonetaryGrant",
                                    "funder": {"@id": ror,
                                                "@type": "Organization",
                                                "name": f"{funder}"},
                                    "identifier": f"{award[i]}",
                                    "name": f"{project[i]}"
                                    })
                elif award:
                    funding.append({"@type": "MonetaryGrant",
                                    "funder": {"@type": "Organization",
                                                "name": f"{funder}"},
                                    "identifier": f"{award[i]}",
                                    "name": f"{project[i]}"
                                    })
                elif ror:
                    funding.append({"@type": "MonetaryGrant",
                                    "funder": {"@id": ror,
                                                "@type": "Organization",
                                                "name": f"{funder}"},
                                    "name": f"{project[i]}"
                                })
                # if ror and award number were not found
                else:
                    funding.append({"@type": "MonetaryGrant",
                                    "funder": {"@type": "Organization",
                                                "name": f"{funder}"},
                                    "name": f"{project[i]}"
                                })
                i += 1
        """if len(funding) != 0:
            if len(funding) == 1:
                funding = funding[0]
        else:"""
        if len(funding) == 0:
            funding = None
        return funding

    def get_license(self) -> Union[List[Dict], None]:
        # Mapping: schema:license = spase:AccessInformation/spase:RightsList/spase:Rights
        # Using schema:license as defined in: https://schema.org/license
        license_url = []

        """<RightsList>
            <Rights xml:lang="en"
            schemeURI="https://spdx.org/licenses/"
            rightsIdentifierScheme="SPDX"
            rightsIdentifier="CC0-1.0"
            rightsURI="https://spdx.org/licenses/CC0-1.0.html">
            Creative Commons Zero v1.0 Universal</Rights>
        </RightsList>"""

        desiredTag = self.desiredRoot.tag.split("}")
        SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:AccessInformation/spase:RightsList/spase:Rights"
        for item in self.metadata.findall(
            SPASE_Location,
            namespaces=self.namespaces,
        ):
            attributes = item.attrib
            if item.get("rightsURI") not in str(license_url):
                attributes["name"] = (item.text).strip()
                license_url.append(attributes)
        if license_url == []:
            license_url = None
        #elif len(license_url) == 1:
        #    license_url = license_url[0]
        return license_url

    def get_was_revision_of(self) -> Union[List[Dict], Dict, None]:
        # Mapping: prov:wasRevisionOf = spase:Association/spase:AssociationID
        #   (if spase:AssociationType is "RevisionOf")
        # prov:wasRevisionOf found at https://www.w3.org/TR/prov-o/#wasRevisionOf
        was_revision_of = get_relation(self.desiredRoot, ["RevisionOf"])
        return was_revision_of

    def get_was_derived_from(self) -> Union[Dict, None]:
        # Mapping: schema:wasDerivedFrom = spase:Association/spase:AssociationID
        #   (if spase:AssociationType is "DerivedFrom" or "ChildEventOf")
        # schema:wasDerivedFrom found at https://www.w3.org/TR/prov-o/#wasDerivedFrom
        was_derived_from = None
        # same mapping as is_based_on
        was_derived_from = self.get_is_based_on()
        return was_derived_from

    def get_is_based_on(self) -> Union[List[Dict], Dict, None]:
        # Mapping: schema:isBasedOn = spase:Association/spase:AssociationID
        #   (if spase:AssociationType is "DerivedFrom" or "ChildEventOf")
        # schema:isBasedOn found at https://schema.org/isBasedOn
        is_based_on = get_relation(self.desiredRoot, ["ChildEventOf", "DerivedFrom"])
        return is_based_on

    def get_was_generated_by(self) -> Union[List[Dict], None]:
        # Mapping: prov:wasGeneratedBy = spase:InstrumentID/spase:ResourceID
        #   and spase:InstrumentID/spase:ResourceHeader/spase:ResourceName
        #   AND spase:InstrumentID/spase:ObservatoryID/spase:ResourceID
        #   and spase:InstrumentID/spase:ObservatoryID/spase:ResourceHeader/spase:ResourceName
        #   AND spase:InstrumentID/spase:ObservatoryID/spase:ObservatoryGroupID/spase:ResourceID
        #   and spase:InstrumentID/spase:ObservatoryID/spase:ObservatoryGroupID/spase:ResourceHeader/spase:ResourceName
        # prov:wasGeneratedBy found at https://www.w3.org/TR/prov-o/#wasGeneratedBy

        instruments = get_instrument(self.metadata, self.file)
        observatories = get_observatory(self.metadata, self.file)
        was_generated_by = []
        
        if observatories:
            for each in observatories:
                was_generated_by.append({"@type": ["ResearchProject", "prov:Activity"],
                                            "prov:used": each})
        if instruments:
            for each in instruments:
                was_generated_by.append({"@type": ["ResearchProject", "prov:Activity"],
                                            "prov:used": each})

        if was_generated_by == []:
            was_generated_by = None
        return was_generated_by


# Below are utility functions for the SPASE strategy.


def get_schema_version(metadata: etree.ElementTree) -> str:
    """
    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The version of the SPASE schema used in the metadata record.
    """
    schema_version = metadata.findtext(
        "{http://www.spase-group.org/data/schema}Version"
    )
    return schema_version

def get_authors(metadata: etree.ElementTree) -> tuple:
    """
    Takes an XML tree and scrapes the desired authors (with their roles), publication date,
    publisher, contributors, and publication title. Also scraped are the names and roles of
    the backups, which are any Contacts found that are not considered authors. It then returns 
    these items, with the author, author roles, and contributors as lists and the rest as strings,
    except for the backups which is a dictionary.

    :param metadata: The SPASE metadata object as an XML tree.
    :type entry: etree.ElementTree object
    :returns: The highest priority authors found within the SPASE record as a list
                as well as a list of their roles, the publication date, publisher,
                contributors, and the title of the publication. It also returns any contacts found,
                along with their role(s) in two separate dictionaries: ones that are not considered
                for the author role and ones that are.
    :rtype: tuple
    """
    # local vars needed
    author = []
    contactsList = {}
    authorRole = []
    pubDate = ""
    pub = ""
    dataset = ""
    backups = {}
    PI_child = None
    root = metadata.getroot()
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt

    # traverse xml to extract needed info
    # iterate thru to find ResourceHeader
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("ResourceHeader"):
            targetChild = child
            # iterate thru to find PublicationInfo
            for child in targetChild:
                try:
                    if child.tag.endswith("PublicationInfo"):
                        PI_child = child
                    elif child.tag.endswith("Contact"):
                        C_Child = child
                        # iterate thru Contact to find PersonID and Role
                        for child in C_Child:
                            try:
                                # find PersonID
                                if child.tag.endswith("PersonID"):
                                    # store PersonID
                                    PersonID = child.text
                                    backups[PersonID] = []
                                    contactsList[PersonID] = []
                                # find Role
                                elif child.tag.endswith("Role"):
                                    # backup author
                                    if ("PrincipalInvestigator" in child.text) or ("PI" in child.text) or ("CoInvestigator" in child.text) or ("Author" in child.text):
                                        if PersonID not in author:
                                            author.append(PersonID)
                                            authorRole.append(child.text)
                                        else:
                                            index = author.index(PersonID)
                                            authorRole[index] = [authorRole[index], child.text]
                                        # store author roles found here in case PubInfo present
                                        contactsList[PersonID] += [child.text]
                                    # backup publisher
                                    elif child.text == "Publisher":
                                        pub = child.text
                                    else:
                                        # use list for values in case one person has multiple roles
                                        # store contacts w non-author roles for use in contributors
                                        backups[PersonID] += [child.text]
                            except AttributeError as err:
                                continue
                except AttributeError as err:
                    continue
    if PI_child is not None:
        for child in PI_child.iter(tag=etree.Element):
            # collect preferred author
            if child.tag.endswith("Authors"):
                author = [child.text]
                authorRole = ["Author"]
            elif child.tag.endswith("PublicationDate"):
                pubDate = child.text
            # collect preferred publisher
            elif child.tag.endswith("PublishedBy"):
                pub = child.text
            # collect preferred dataset
            elif child.tag.endswith("Title"):
                dataset = child.text

    # remove contacts w/o role values
    contactsCopy = {}
    cleanedBackups = {}
    for contact, role in contactsList.items():
        if role:
            contactsCopy[contact] = role
    for contact, role in backups.items():
        if role:
            cleanedBackups[contact] = role
    # compare author and contactsList to add author roles from contactsList for matching people found in PubInfo
    # also formats the author list correctly for use in get_creator
    author, authorRole, contactsList = process_authors(author, authorRole, contactsCopy)
    # remove authors from backups if not considered a ContactPerson or DataCurator
    DC_Roles = {}
    DC_Roles["ContactPerson"] = ["GeneralContact", "HostContact", "MetadataContact", "TechnicalContact"]
    DC_Roles["DataCurator"] = ["ArchiveSpecialist"]
    backupsCopy = copy.deepcopy(cleanedBackups)
    for each in author:
        for key, val in backupsCopy.items():
            # pulled from contacts
            if "spase" in each:
                if each == key:
                    for role in val:
                        if not (role in DC_Roles["ContactPerson"] or role in DC_Roles["DataCurator"]):
                            cleanedBackups.pop(key)
            # pulled from PubInfo authors
            else:
                # use nameSplitter to separate cleanedBackups key into family and givenName
                #   to compare to author string
                author_str, given_name, family_name = name_splitter(key)
                if each == (family_name + ", " + given_name):
                    for role in val:
                        if not (role in DC_Roles["ContactPerson"] or role in DC_Roles["DataCurator"]):
                            cleanedBackups.pop(key)
    return author, authorRole, pubDate, pub, dataset, cleanedBackups, contactsList

def get_accessURLs(metadata: etree.ElementTree) -> tuple:
    """
    :param metadata: The SPASE metadata object as an XML tree.
    
    :returns: The AccessURLs found in the SPASE record, separated into two dictionaries,
                dataDownloads and potentialActions, depending on if they are a direct 
                link to data or not. These dictionaries are setup to have the keys as
                the url and the values to be a list containing their data format(s)
                (and product key if applicable).
    """
    # needed local vars
    dataDownloads = {}
    potentialActions = {}
    AccessURLs = {}
    encoding = []
    encoder = []
    i = 0
    j = 0
    root = metadata.getroot()
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt

    # get Formats before iteration due to order of elements in SPASE record
    desiredTag = desiredRoot.tag.split("}")
    SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:AccessInformation/spase:Format"
    for item in metadata.findall(SPASE_Location, namespaces={"spase": "http://www.spase-group.org/data/schema"}):
        encoding.append(item.text)

    # traverse xml to extract needed info
    # iterate thru children to locate Access Information
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("AccessInformation"):
            targetChild = child
            # iterate thru children to locate AccessURL and Format
            for child in targetChild:
                if child.tag.endswith("AccessURL"):
                    targetChild = child
                    # iterate thru children to locate URL
                    for child in targetChild:
                        if child.tag.endswith("URL"):
                            url = child.text
                            # provide "NULL" value in case no keys are found
                            AccessURLs[url] = []
                            # append an encoder for each URL
                            encoder.append(encoding[j])
                        # check if URL has a product key
                        elif child.tag.endswith("ProductKey"):
                            prodKey = child.text
                            # if only one prodKey exists
                            if AccessURLs[url] == []:
                                AccessURLs[url] = [prodKey]
                            # if multiple prodKeys exist
                            else:
                                AccessURLs[url] += [prodKey]
            j += 1
    for k, v in AccessURLs.items():
        # if URL has no access key
        if not v:
            NonDataFileExt = ['html', 'com', 'gov', 'edu', 'org', 'eu', 'int']
            DataFileExt = ['csv', 'cdf', 'fits', 'txt', 'nc', 'jpeg',
                            'png', 'gif', 'tar', 'netcdf3', 'netcdf4', 'hdf5',
                            'zarr', 'asdf', 'zip']
            protocol, sep, domain = k.partition("://")
            domain, sep, downloadFile = domain.rpartition("/")
            downloadFile, sep, ext = downloadFile.rpartition(".")
            # see if file extension is one associated w data files
            if ext not in DataFileExt:
                downloadable = False
            else:
                downloadable = True
            # if URL is direct link to download data, add to the dataDownloads dictionary
            if downloadable:
                dataDownloads[k] = [encoder[i]]
            else:
                potentialActions[k] = [encoder[i], "None"]
        # if URL has access key, add to the potentialActions dictionary
        else:
            potentialActions[k] = [encoder[i], v]
        i += 1
    return dataDownloads, potentialActions

def get_dates(metadata: etree.ElementTree) -> tuple:
    """
    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The ReleaseDate and a list of all the dates found in RevisionHistory
    """
    root = metadata.getroot()
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt
    RevisionHistory = []
    ReleaseDate = ""

    # traverse xml to extract needed info
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("ResourceHeader"):
            targetChild = child
            for child in targetChild:
                # find ReleaseDate and construct datetime object from the string
                try:
                    if child.tag.endswith("ReleaseDate"):
                        date, sep, time = child.text.partition("T")
                        if "Z" in child.text:
                            time = time.replace("Z", "")
                        if "." in child.text:
                            time, sep, after = time.partition(".")
                        dt_string = date + " " + time
                        dt_obj = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
                        ReleaseDate = dt_obj
                    elif child.tag.endswith("RevisionHistory"):
                        RHChild = child
                        for child in RHChild:
                            REChild = child
                            for child in REChild:
                                if child.tag.endswith("ReleaseDate"):
                                    date, sep, time = child.text.partition("T")
                                    if "Z" in child.text:
                                        time = time.replace("Z", "")
                                    if "." in child.text:
                                        time, sep, after = time.partition(".")
                                    dt_string = date + " " + time
                                    try:
                                        dt_obj = datetime.strptime(dt_string,
                                                                "%Y-%m-%d %H:%M:%S")
                                    # catch error when RevisionHistory is not formatted w time
                                    except ValueError as err:
                                        dt_obj = datetime.strptime(dt_string.strip(),
                                                                "%Y-%m-%d").date()
                                    finally:
                                        RevisionHistory.append(dt_obj)
                except AttributeError as err:
                    continue
    return ReleaseDate, RevisionHistory

def get_repoID(metadata: etree.ElementTree) -> str:
    """
    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The RepositoryID found in the last AccessInformation section
    """
    root = metadata.getroot()
    repoID = None
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt
    # traverse xml to extract needed info
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("AccessInformation"):
            targetChild = child
            # iterate thru children to locate RepositoryID
            for child in targetChild:
                if child.tag.endswith("RepositoryID"):
                    repoID = child.text
    return repoID

def person_format(
    person_type: str,
    role_name: Union[str, List],
    name: str,
    given_name: str,
    family_name: str,
    affiliation="",
    orcid_id="",
    ror="",
    first_entry=False,
) -> Dict:
    """
    Groups up all available metadata associated with a given contact
    into a dictionary following the SOSO guidelines.

    :param person_type: The type of person being formatted. Values can be either:
        contributor or creator.
    :param role_name: The value found in the Role field associated with this Contact
    :param name: The full name of the Contact, as formatted in the SPASE record
    :param given_name: The first name/initial and middle name/initial of the Contact
    :param family_name: The last name of the Contact
    :param affiliation: The organization this Contact is affiliated with.
    :param orcid_id: The ORCiD identifier for this Contact
    :param ror: The ROR ID for the associated affiliation
    :param first_entry: Boolean signifying if this person is the
        first entry into its respective property result.

    :returns: The entry in the correct format to append to the contributor or creator dictionary
    """

    *_, orcid_val = orcid_id.rpartition("/")
    entry = None
    # most basic format for creator item
    if person_type == "creator":
        entry = {
            "@type": "Person",
            "name": name
        }
        if given_name and family_name:
            entry["familyName"] = family_name
            entry["givenName"] = given_name

    elif person_type == "contributor":
        # Split string on uppercase characters
        res = re.split(r"(?=[A-Z])", role_name)
        # Remove empty strings and join with space or hypen depending on role_name
        if "Co" in role_name:
            pattern = r"{}(?=[A-Z])".format(re.escape("Co"))
            if bool(re.search(pattern, role_name)):
                pretty_name = "-".join(filter(None, res))
            else:
                pretty_name = " ".join(filter(None, res))
        else:
            pretty_name = " ".join(filter(None, res))
        # most basic format for contributor item
        entry = {
            "@type": ["Role", "DefinedTerm"],
            "contributor": {
                "@type": "Person",
                "name": name
            },
            "inDefinedTermSet": {
                "@id": "https://spase-group.org/data/model/spase-latest/spase-latest_xsd.htm#Role"
            },
            "roleName": pretty_name,
            "termCode": role_name,
        }

        if given_name and family_name:
            entry["contributor"]["familyName"] = family_name
            entry["contributor"]["givenName"] = given_name

        if first_entry:
            entry["inDefinedTermSet"]["@type"] = "DefinedTermSet"
            entry["inDefinedTermSet"]["name"] = "SPASE Role"
            entry["inDefinedTermSet"][
                "url"
            ] = "https://spase-group.org/data/model/spase-latest/spase-latest_xsd.htm#Role"

    if orcid_id:
        if person_type == "contributor":
            entry["contributor"]["identifier"] = {
                "@id": f"https://orcid.org/{orcid_id}",
                "@type": "PropertyValue",
                "propertyID": "https://registry.identifiers.org/registry/orcid",
                "url": f"https://orcid.org/{orcid_id}",
                "value": f"orcid:{orcid_val}",
            }
            entry["contributor"]["@id"] = f"https://orcid.org/{orcid_id}"
        else:
            entry["identifier"] = {
                "@id": f"https://orcid.org/{orcid_id}",
                "@type": "PropertyValue",
                "propertyID": "https://registry.identifiers.org/registry/orcid",
                "url": f"https://orcid.org/{orcid_id}",
                "value": f"orcid:{orcid_val}",
            }
            entry["@id"] = f"https://orcid.org/{orcid_id}"
    if affiliation:
        if person_type == "contributor":
            if ror:
                entry["contributor"]["affiliation"] = {
                    "@type": "Organization",
                    "name": affiliation,
                    "identifier": {
                        "@id": f"https://ror.org/{ror}",
                        "@type": "PropertyValue",
                        "propertyID": "https://registry.identifiers.org/registry/ror",
                        "url": f"https://ror.org/{ror}",
                        "value": f"ror:{ror}",
                    },
                }
            else:
                entry["contributor"]["affiliation"] = {
                    "@type": "Organization",
                    "name": affiliation,
                }
        else:
            if ror:
                entry["affiliation"] = {
                    "@type": "Organization",
                    "name": affiliation,
                    "identifier": {
                        "@id": f"https://ror.org/{ror}",
                        "@type": "PropertyValue",
                        "propertyID": "https://registry.identifiers.org/registry/ror",
                        "url": f"https://ror.org/{ror}",
                        "value": f"ror:{ror}",
                    },
                }
            else:
                entry["affiliation"] = {"@type": "Organization", "name": affiliation}

    return entry

def name_splitter(person: str) -> tuple[str, str, str]:
    """
    Splits the given PersonID found in the SPASE Contacts container into
    three separate strings holding their full name, first name (and middle initial),
    and last name.

    :param person: The string found in the Contacts field as is formatted in the SPASE record.

    :returns: The string containing the full name of the Contact, the string
        containing the first name/initial of the Contact,
        and the string containing the last name of the Contact
    """
    if person:
        *_, name_str = person.partition("Person/")
        # get rid of extra quotations
        name_str = name_str.replace("'", "")
        if "." in name_str:
            given_name, _, family_name = name_str.partition(".")
            # if name has initial(s)
            if "." in family_name:
                initial, _, family_name = family_name.partition(".")
                if len(initial) > 1:
                    initial = initial[0]
                given_name = given_name + " " + initial + "."
            name_str = given_name + " " + family_name
            name_str = name_str.replace('"', "")
        else:
            given_name = ""
            family_name = ""
    else:
        raise ValueError(
            "This function only takes a nonempty string as an argument. Try again."
        )
    return name_str, given_name, family_name

def get_information_url(metadata: etree.ElementTree) -> Union[List[Dict], None]:
    """
    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The name, description, and url(s) for all InformationURL sections found in the ResourceHeader,
                formatted as a list of dictionaries.
    """
    root = metadata.getroot()
    information_url = []
    name = ""
    description = ""
    for elt in root.iter(tag=etree.Element):
        if (elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData")
            or elt.tag.endswith("Observatory") or elt.tag.endswith("Instrument")):
            desiredRoot = elt
    # traverse xml to extract needed info
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("ResourceHeader"):
            targetChild = child
            # iterate thru children to locate AccessURL and Format
            for child in targetChild:
                try:
                    if child.tag.endswith("InformationURL"):
                        targetChild = child
                        # iterate thru children to locate URL
                        for child in targetChild:
                            if child.tag.endswith("Name"):
                                name = child.text
                            elif child.tag.endswith("URL"):
                                url = child.text
                            elif child.tag.endswith("Description"):
                                description = child.text
                        if name:
                            if description:
                                information_url.append({"name": name,
                                                        "url": url,
                                                        "description": description})
                            else:
                                information_url.append({"name": name,
                                                        "url": url})
                        else:
                            information_url.append({"url": url})
                except AttributeError:
                    continue
    if information_url == []:
        information_url = None
    return information_url

def get_instrument(metadata: etree.ElementTree, path: str) -> Union[List[Dict], None]:
    """
    :param metadata: The SPASE metadata object as an XML tree.
    :param path: The absolute file path of the XML file the user wishes to pull info from.

    :returns: The name, url, and ResourceID for each instrument found in the InstrumentID section,
                formatted as a list of dictionaries.
    """
    # Mapping: schema:IndividualProduct, prov:Entity, and sosa:System = spase:InstrumentID
    # schema:IndividualProduct found at https://schema.org/IndividualProduct
    # prov:Entity found at https://www.w3.org/TR/prov-o/#Entity
    # sosa:System found at https://w3c.github.io/sdw-sosa-ssn/ssn/#SOSASystem

    root = metadata.getroot()
    instrument = []
    instrumentIDs = {}
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("InstrumentID"):
            instrumentIDs[child.text] = {}
    if instrumentIDs == {}:
        instrument = None
    else:
        # follow link provided by instrumentID to instrument page
        # from there grab name and url
        for item in instrumentIDs:
            instrumentIDs[item]["name"] = ""
            instrumentIDs[item]["URL"] = ""
            if "Dev/" in path:
                absPath, sep, after = path.partition("Dev/")
            else:
                absPath, sep, after = path.partition("NASA/")
            record = absPath + item.replace("spase://","") + ".xml"
            record = record.replace("'","")
            if os.path.isfile(record):
                testSpase = SPASE(record)
                root = testSpase.metadata.getroot()
                instrumentIDs[item]["name"] = testSpase.get_name()
                instrumentIDs[item]["URL"] = testSpase.get_url()
            else:
                print(f"Could not access associated SPASE record: {item}")
                continue
        for k in instrumentIDs.keys():
            if instrumentIDs[k]["URL"]:
                instrument.append({"@id": instrumentIDs[k]["URL"],
                                                "@type": ["IndividualProduct", "prov:Entity", "sosa:System"],
                                                "identifier": {"@type": "PropertyValue",
                                                                "propertyID": "SPASE Resource ID",
                                                                "value": k},
                                                "name": instrumentIDs[k]["name"],
                                                "url": instrumentIDs[k]["URL"]})
    return instrument

def get_observatory(metadata: etree.ElementTree, path: str) -> Union[List[Dict], None]:
    """
    :param metadata: The SPASE metadata object as an XML tree.
    :param path: The absolute file path of the XML file the user wishes to pull info from.

    :returns:   The name, url, and ResourceID for each observatory related to this dataset,
                formatted as a list of dictionaries.
    """
    # Mapping: schema:ResearchProject, prov:Entity, and sosa:Platform = spase:InstrumentID/spase:ObservatoryID
    #   AND spase:InstrumentID/spase:ObservatoryID/spase:ObservatoryGroupID if available
    # schema:ResearchProject found at https://schema.org/ResearchProject
    # prov:Entity found at https://www.w3.org/TR/prov-o/#Entity
    # sosa:Platform found at https://w3c.github.io/sdw-sosa-ssn/ssn/#SOSAPlatform

    instrument = get_instrument(metadata, path)
    if instrument is not None:
        observatory = []
        observatoryGroupID = ""
        observatoryID = ""
        recordedIDs = []
        instrumentIDs = []

        for each in instrument:
            instrumentIDs.append(each["identifier"]["value"])
        for item in instrumentIDs:
            if "Dev/" in path:
                absPath, sep, after = path.partition("Dev/")
            elif "ESA/" in path:
                absPath, sep, after = path.partition("ESA/")
            else:
                absPath, sep, after = path.partition("NASA/")
            record = absPath + item.replace("spase://","") + ".xml"
            record = record.replace("'","")
            # follow link provided by instrument to instrument page, from there grab ObservatoryID
            if os.path.isfile(record):
                testSpase = SPASE(record)
                root = testSpase.metadata.getroot()
                for elt in root.iter(tag=etree.Element):
                    if elt.tag.endswith("Instrument"):
                        desiredRoot = elt
                for child in desiredRoot.iter(tag=etree.Element):
                    if child.tag.endswith("ObservatoryID"):
                        observatoryID = child.text
                # use observatoryID as record to get observatoryGroupID and other info              
                record = absPath + observatoryID.replace("spase://","") + ".xml"
                record = record.replace("'","")                
                if os.path.isfile(record):
                    url = ""
                    testSpase = SPASE(record)
                    root = testSpase.metadata.getroot()
                    for elt in root.iter(tag=etree.Element):
                        if elt.tag.endswith("Observatory"):
                            desiredRoot = elt
                    for child in desiredRoot.iter(tag=etree.Element):
                        if child.tag.endswith("ObservatoryGroupID"):
                            observatoryGroupID = child.text
                    name = testSpase.get_name()
                    url = testSpase.get_url()
                    # finally, follow that link to grab name and url from there
                    if observatoryGroupID:
                        record = absPath + observatoryGroupID.replace("spase://","") + ".xml"
                        record = record.replace("'","") 
                        if os.path.isfile(record):
                            groupURL = ""
                            testSpase = SPASE(record)
                            groupName = testSpase.get_name()
                            groupURL = testSpase.get_url()
                            if groupURL:
                                if observatoryGroupID not in recordedIDs:
                                    observatory.append({"@type": ["ResearchProject", "prov:Entity", "sosa:Platform"],
                                                        "@id": groupURL,
                                                        "name": groupName,
                                                        "identifier": {"@type": "PropertyValue",
                                                                        "propertyID": "SPASE Resource ID",
                                                                        "value": observatoryGroupID},
                                                        "url": groupURL})
                                    recordedIDs.append(observatoryGroupID)
                        else:
                            #print(f"Could not access associated SPASE record: {observatoryGroupID}")
                            continue
                    if url and (observatoryID not in recordedIDs):
                        observatory.append({"@type": ["ResearchProject", "prov:Entity", "sosa:Platform"],
                                            "@id": url,
                                            "name": name,
                                            "identifier": {"@type": "PropertyValue",
                                                                        "propertyID": "SPASE Resource ID",
                                                                        "value": observatoryID},
                                            "url": url})
                        recordedIDs.append(observatoryID)
                else:
                    #print(f"Could not access associated SPASE record: {observatoryID}")
                    continue
    else:
        observatory = None
    return observatory

def get_alternate_name(metadata: etree.ElementTree) -> Union[str, None]:
    """
    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The alternate name of the dataset as a string.
    """
    root = metadata.getroot()
    alternate_name = None
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt
    for child in desiredRoot.iter(tag=etree.Element):
        if child.tag.endswith("ResourceHeader"):
            targetChild = child
            # iterate thru children to locate AlternateName for dataset
            for child in targetChild:
                try:
                    if child.tag.endswith("AlternateName"):
                        alternate_name = child.text
                except AttributeError:
                    continue
    return alternate_name

def get_cadenceContext(cadence:str) -> str:
    """
    :param cadence: The value found in the Cadence field of the TemporalDescription section

    :returns: A string description of what this value represents/means.
    """
    # takes cadence/repeatFreq and returns an explanation for what it means
    # ISO 8601 Format = PTHH:MM:SS.sss
    # P1D, P1M, and P1Y represent time cadences of one day, one month, and one year, respectively
    context = "The time series is periodic with a "
    start, sep, end = cadence.partition("P")
    # cadence is in hrs, min, or sec
    if "T" in end:
        start, sep, time = end.partition("T")
        if "H" in time:
            # hrs
            start, sep, end = time.partition("H")
            context += start + " hour cadence"
        elif "M" in time:
            # min
            start, sep, end = time.partition("M")
            context += start + " minute cadence"
        elif "S" in time:
            # sec
            start, sep, end = time.partition("S")
            context += start + " second cadence"
    # one of the 3 base cadences
    else:
        if "D" in end:
            # days
            start, sep, end = end.partition("D")
            context += start + " day cadence"
        elif "M" in end:
            # months
            start, sep, end = end.partition("M")
            context += start + " month cadence"
        elif "Y" in end:
            # yrs
            start, sep, end = end.partition("Y")
            context += start + " year cadence"
    if context == "This means that the time series is periodic with a ":
        context = None
    return context

def get_mentions(metadata: etree.ElementTree) -> Union[List[Dict], Dict, None]:
    """
    Scrapes any AssociationIDs with the AssociationType "Other" and formats them
    as dictionaries using the get_relation function.

    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The ID's of other SPASE records related to this one in some way.
    """
    # Mapping: schema:mentions = spase:Association/spase:AssociationID
    #   (if spase:AssociationType is "Other")
    # schema:mentions found at https://schema.org/mentions
    root = metadata.getroot()
    desired_root = None
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desired_root = elt
    mentions = get_relation(desired_root, ["Other"])
    return mentions

def get_is_part_of(metadata: etree.ElementTree) -> Union[List[Dict], Dict, None]:
    """
    Scrapes any AssociationIDs with the AssociationType "PartOf" and formats them
    as dictionaries using the get_relation function.

    :param metadata: The SPASE metadata object as an XML tree.

    :returns: The ID(s) of the larger resource this SPASE record is a portion of, as a dictionary.
    """
    # Mapping: schema:isBasedOn = spase:Association/spase:AssociationID
    #   (if spase:AssociationType is "PartOf")
    # schema:isPartOf found at https://schema.org/isPartOf
    root = metadata.getroot()
    desired_root = None
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desired_root = elt
    is_part_of = get_relation(desired_root, ["PartOf"])
    return is_part_of

def get_ORCiD_and_Affiliation(PersonID: str) -> tuple:
    """
    :param PersonID: The SPASE ID linking the page with the Person's info.

    :returns: The ORCiD ID and organization name (with its ROR ID, if found) this Contact is affiliated with, as strings.
    """
    # takes PersonID and follows its link to get ORCIdentifier and OrganizationName
    orcidID = ""
    affiliation = ""
    ror = ""

    # get home directory
    home_dir = str(Path.home())
    home_dir = home_dir.replace("\\", "/")
    # get current working directory
    cwd = str(Path.cwd()).replace("\\", "/")
    # see if file is one that has been adjusted locally
    *_, file_name = PersonID.rpartition("/")
    file_path = os.path.join(f"{cwd}/ExternalSPASE_XMLs/", f"spase-{file_name}.xml")
    #print("file path is " + file_path)
    if os.path.isfile(file_path):
        record = home_dir + "/Dev/SPASE-DataCite/ExternalSPASE_XMLs/" + f"spase-{file_name}" + ".xml"
    else:
        record = home_dir + PersonID.replace("spase://","/") + ".xml"
    record = record.replace("'","")
    #print("record is " + record)
    if os.path.isfile(record):
        testSpase = SPASE(record)
        root = testSpase.metadata.getroot()
        # iterate thru xml to get desired info
        for elt in root.iter(tag=etree.Element):
            if elt.tag.endswith("Person"):
                desiredRoot = elt
        for child in desiredRoot.iter(tag=etree.Element):
            if child.tag.endswith("ORCIdentifier"):
                orcidID = child.text
            elif child.tag.endswith("OrganizationName"):
                affiliation = child.text
            elif child.tag.endswith("RORIdentifier"):
                ror = child.text
    else:
        raise ValueError("Could not access associated SPASE record.")
    return orcidID, affiliation, ror

def get_temporal(metadata: etree.ElementTree, namespaces: Dict) -> Union[List, None]:
    """
    :param metadata: The SPASE metadata object as an XML tree.
    :param namespaces: The SPASE namespaces used in the form of a dictionary.

    :returns: The cadence or common time interval between the start of successive measurements,
                given in its ISO 8601 formatting as well as a explanation sentence.
    """
    # Mapping: schema:temporal = spase:TemporalDescription/spase:Cadence
    # Each object is:
    #   [ explanation (string explaining meaning of cadence), Cadence]
    # Schema found at https://schema.org/temporal
    root = metadata.getroot()
    for elt in root.iter(tag=etree.Element):
        if elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData"):
            desiredRoot = elt
    
    desiredTag = desiredRoot.tag.split("}")
    SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:TemporalDescription/spase:Cadence"
    repeat_frequency =  metadata.findtext(
        SPASE_Location,
        namespaces= namespaces,
    )

    explanation = ""

    if repeat_frequency:
        explanation = get_cadenceContext(repeat_frequency)
        temporal = [explanation, repeat_frequency]
    else:
        temporal = None
    return temporal

def get_metadata_license(metadata: etree.ElementTree) -> str:
    """
    :param metadata: The metadata object as an XML tree.

    :returns: The metadata license of the SPASE record.
    """
    metadata_license = None
    root = metadata.getroot()
    attributes = root.attrib
    # key looks like this: {http://www.w3.org/2001/XMLSchema-instance}rights
    for key, val in attributes.items():
        if "rights" in key:
            metadata_license = val
    return metadata_license

def process_authors(
    author: List, author_role: List, contacts_list: Dict
) -> tuple[List, List, Dict]:
    """
    Groups any contact names from the SPASE Contacts container with their matching names, if
    found, in PubInfo:Authors, and adds any additional author roles (such as PI) to their
    corresponding entry in the author_roles list. Any contact with an author role not
    listed in PubInfo:Authors is added to the contacts_list with the rest of the
    non-matching contacts for use in get_contributors. Lastly, authors selected from
    Contacts when no PubInfo:Authors are re-ordered according to priority list.

    :param author: The list of names found in SPASE record to be used in get_creator
    :param author_role: The list of roles associated with each person found in author list
    :param contacts_list: The dictionary containing the names of people considered to
                            be authors as formatted in the Contacts container in the
                            SPASE record, as well as their roles

    :returns: The updated author, author_roles, and contacts_list items after merging any author
                roles from Contacts with the roles associated with them if found in PubInfo.
    """
    # loop thru all contacts to find any that match authors, unless no PubInfo was found
    # if matches found, add roles to author_roles and remove them from contacts_list
    # if no match found for person(s), leave in contacts_list for use in get_contributors

    author_str = str(author).replace("[", "").replace("]", "")
    # if creators were found in Contact/PersonID (no PubInfo)
    # remove author roles from contacts_list so not duplicated in contributors
    #   (since already in author list), and order those in authors list in
    #   terms of priority
    if "Person/" in author_str:
        contacts_copy = {}
        for person, val in contacts_list.items():
            contacts_copy[person] = []
            for role in val:
                # if role is not considered for author, add to acceptable roles
                #   list for use in contributors
                if (
                    ("PrincipalInvestigator" not in role)
                    and ("PI" not in role)
                    and ("CoInvestigator" not in role)
                    and ("Author" not in role)
                ):
                    contacts_copy[person].append(role)
            # if no acceptable roles were found, remove that author from contributor consideration
            if contacts_copy[person] == []:
                contacts_copy.pop(person)
        # order backup authors according to following roles list
        author_ordered = []
        author_role_ordered = []
        roles = ["Author", "PrincipalInvestigator", "MissionPrincipalInvestigator",
            "CoPI", "DeputyPI", "FormerPI", "CoInvestigator"]
        for role in roles:
            for num, creator in enumerate(author):
                if author_role[num] == role:
                    if creator not in author_ordered:
                        author_ordered.append(creator)
                        author_role_ordered.append(author_role[num])
        return author_ordered, author_role_ordered, contacts_copy
    # if all creators were found in PublicationInfo/Authors
    else:
        # if there are multiple authors
        if ("; " in author_str) or ("., " in author_str) or (" and " in author_str) or (" & " in author_str):
            if ";" in author_str:
                author = author_str.split("; ")
            elif ".," in author_str:
                author = author_str.split("., ")
            elif " and " in author_str:
                author = author_str.split(" and ")
            else:
                author = author_str.split(" & ")
            # fix num of roles
            while len(author_role) < len(author):
                author_role += ["Author"]
            # get rid of extra quotations
            for num, each in enumerate(author):
                if "'" in each:
                    author[num] = each.replace("'", "")
            # iterate over each person in author string
            for person in author:
                index = author.index(person)
                # if first name doesnt have a period, check if it is an initial
                if not person.endswith("."):
                    # if first name is an initial w/o a period, add one
                    grp = re.search(r"[\.\s]{1}[\w]{1}$", person)
                    if grp is not None:
                        person += "."
                # remove 'and' from name
                if "and " in person:
                    person = person.replace("and ", "")
                # continued formatting fixes
                if ", " in person:
                    family_name, _, given_name = person.partition(", ")
                else:
                    given_name, _, family_name = person.partition(". ")
                    given_name += "."
                if "," in given_name:
                    given_name = given_name.replace(",", "")
                # iterate thru contacts to find one that matches the current person
                contacts_list, author_role = findMatch(contacts_list, person, author_role, index)
                author[index] = (f"{family_name}, {given_name}").strip()
        # if there is only one author listed
        else:
            # get rid of extra quotations
            person = author_str.replace('"', "")
            person = author_str.replace("'", "")
            # if author is a person (assuming names contain a comma)
            if ", " in person:
                family_name, _, given_name = person.partition(", ")
                # also used when there are 3+ comma separated orgs 
                #   listed as authors - not intended (how to fix?)
                if "," in given_name:
                    given_name = given_name.replace(",", "")
                # iterate thru contacts to find one that matches the current person
                contacts_list, author_role = findMatch(contacts_list, person, author_role, 0)
                author[0] = (f"{family_name}, {given_name}").strip()
            else:
                # handle case when assumption 'names have commas' fails
                if ". " in person:
                    given_name, _, family_name = person.partition(". ")
                    if " " in family_name:
                        initial, _, family_name = family_name.partition(" ")
                        given_name = given_name + ". " + initial[0] + "."
                    # iterate thru contacts to find one that matches the current person
                    contacts_list, author_role = findMatch(contacts_list, person, author_role, 0)
                    author[0] = (f"{family_name}, {given_name}").strip()
                # author is an organization, so no splitting is needed
                else:
                    author[0] = person.strip()
    return author, author_role, contacts_list

def verify_type(url: str) -> tuple[bool, bool, dict]:
    """
    Verifies that the link found in AssociationID is to a dataset or journal article and acquires
    more information if a dataset is not hosted by NASA.

    :param url: The link provided as an Associated work/reference for the SPASE record

    :returns: Boolean values signifying if the link is a Dataset/ScholarlyArticle.
                Also a dictionary with additional info about the related Dataset
                acquired from DataCite API if it is not hosted by NASA.
    """
    # tests SPASE records to make sure they are datasets or a journal article
    is_dataset = False
    is_article = False
    non_spase_info = {}
    if url is not None:
        if "hpde.io" in url:
            if "Data" in url:
                is_dataset = True
        # case where url provided is a DOI
        else:
            link = requests.head(url, timeout=30)
            # check to make sure doi resolved to an hpde.io page
            if "hpde.io" in link.headers["location"]:
                if "Data" in link.headers["location"]:
                    is_dataset = True
            # if not, call DataCite API to check resourceTypeGeneral
            #   property associated w the record
            else:
                *_, doi = url.partition("doi.org/")
                # dataciteLink = f"https://api.datacite.org/dois/{doi}"
                # headers = {"accept": "application/vnd.api+json"}
                # response = requests.get(dataciteLink, headers=headers)
                response = requests.get(
                    f"https://api.datacite.org/application/vnd.datacite.datacite+json/{doi}",
                    timeout=30,
                )
                if response.raise_for_status() is None:
                    datacite_dict = json.loads(response.text)
                    if "resourceType" in datacite_dict["types"].keys():
                        if datacite_dict["types"]["resourceType"]:
                            if datacite_dict["types"]["resourceType"] == "Dataset":
                                is_dataset = True
                            elif (
                                datacite_dict["types"]["resourceType"]
                                == "JournalArticle"
                            ):
                                is_article = True
                        else:
                            if (
                                datacite_dict["types"]["resourceTypeGeneral"]
                                == "Dataset"
                            ):
                                is_dataset = True
                            elif (
                                datacite_dict["types"]["resourceTypeGeneral"]
                                == "JournalArticle"
                            ):
                                is_article = True
                    else:
                        if datacite_dict["types"]["resourceTypeGeneral"] == "Dataset":
                            is_dataset = True
                        elif (
                            datacite_dict["types"]["resourceTypeGeneral"]
                            == "JournalArticle"
                        ):
                            is_article = True
                        # if wish to add more checks, simply add more "elif" stmts like above
                        # and adjust provenance/relationship functions to include new type check
                    if is_dataset:
                        # grab name, description, license, and creators
                        non_spase_info["name"] = datacite_dict["titles"][0]["title"]
                        if datacite_dict["descriptions"]:
                            non_spase_info["description"] = datacite_dict[
                                "descriptions"
                            ][0]["description"]
                        else:
                            non_spase_info["description"] = (
                                f"No description currently available for {url}."
                            )
                        if datacite_dict["rightsList"]:
                            non_spase_info["license"] = []
                            for each in datacite_dict["rightsList"]:
                                non_spase_info["license"].append(each["rightsUri"])
                        for creator in datacite_dict["creators"]:
                            if ("givenName" in creator.keys()) and (
                                "familyName" in creator.keys()
                            ):
                                family_name = creator["familyName"]
                                given_name = creator["givenName"]
                            elif ", " in creator["name"]:
                                family_name, _, given_name = creator["name"].partition(
                                    ", "
                                )
                            else:
                                family_name = ""
                                given_name = ""
                            # adjust DataCite format to conform to schema.org format
                            if creator["affiliation"]:
                                non_spase_info["creators"] = person_format(
                                    "creator",
                                    "",
                                    creator["name"],
                                    given_name,
                                    family_name,
                                    creator["affiliation"]["name"],
                                )
                            else:
                                non_spase_info["creators"] = person_format(
                                    "creator",
                                    "",
                                    creator["name"],
                                    given_name,
                                    family_name,
                                )
    return is_dataset, is_article, non_spase_info

def get_ResourceID(metadata: etree.ElementTree, namespaces: Dict):
    """
    :param metadata: The SPASE metadata object as an XML tree.
    :param namespaces: The SPASE namespaces used in the form of a dictionary.

    :returns: The ResourceID for the SPASE record.
    """
    root = metadata.getroot()
    for elt in root.iter(tag=etree.Element):
        if (elt.tag.endswith("NumericalData") or elt.tag.endswith("DisplayData")
                or elt.tag.endswith("Observatory") or elt.tag.endswith("Instrument")
                or elt.tag.endswith("Person")):
            desiredRoot = elt

    desiredTag = desiredRoot.tag.split("}")
    SPASE_Location = ".//spase:" + f"{desiredTag[1]}/spase:ResourceID"
    dataset_id = metadata.findtext(
        SPASE_Location, namespaces=namespaces
    )
    return dataset_id

def get_relation(desired_root: etree.Element, association: list[str]) -> Union[List[Dict], Dict, None]:
    """
    Scrapes through the SPASE record and returns the AssociationIDs which have the
    given AssociationType. These are formatted as dictionaries and use the verify_type
    function to add the correct type to each entry.

    :param desired_root: The element in the SPASE metadata tree object we are searching from.
    :param association: The AssociationType(s) we are searching for in the SPASE record.

    :returns: The ID's of other SPASE records related to this one in some way.
    """
    relations = []
    assoc_id = ""
    assoc_type = ""
    relational_records = {}
    # iterate thru xml to find desired info
    if desired_root is not None:
        for child in desired_root.iter(tag=etree.Element):
            if child.tag.endswith("Association"):
                target_child = child
                for child in target_child:
                    if child.tag.endswith("AssociationID"):
                        assoc_id = child.text
                    elif child.tag.endswith("AssociationType"):
                        assoc_type = child.text
                for each in association:
                    if assoc_type == each:
                        relations.append(assoc_id)
        if not relations:
            relation = None
        else:
            i = 0
            # try and get DOI instead of SPASE ID
            for record in relations:
                # get home directory
                home_dir = str(Path.home()).replace("\\", "/")
                # get current working directory
                cwd = str(Path.cwd()).replace("\\", "/")
                # format record
                *_, file_name = record.rpartition("/")
                file_path = os.path.join(f"{cwd}/ExternalSPASE_XMLs/", f"spase-{file_name}.xml")
                #print("file path is " + file_path)
                if os.path.isfile(file_path):
                    record = home_dir + "/Dev/SPASE-DataCite/ExternalSPASE_XMLs/" + f"spase-{file_name}" + ".xml"
                else:
                    record = home_dir + record.replace("spase://","/") + ".xml"
                record = record.replace("'", "")
                if os.path.isfile(record):
                    test_spase = SPASE(record)
                    url = test_spase.get_url()
                    name = test_spase.get_name()
                    description = test_spase.get_description()
                    spase_license = test_spase.get_license()
                    creators = test_spase.get_creator()
                    if creators is None:
                        creators = "No creators were found. View record for contacts."
                    relational_records[url] = {
                        "name": name,
                        "description": description,
                        "creators": creators,
                    }
                    if spase_license is not None:
                        relational_records[url]["license"] = spase_license
                i += 1
            relation = []
            # not SPASE records
            if not relational_records:
                for each in relations:
                    # most basic entry into relation
                    entry = {"@id": each, "identifier": each, "url": each}
                    is_dataset, is_article, non_spase_info = verify_type(each)
                    if is_dataset:
                        entry["@type"] = "Dataset"
                        entry["name"] = non_spase_info["name"]
                        entry["description"] = non_spase_info["description"]
                        if "license" in non_spase_info.keys():
                            entry["license"] = non_spase_info["license"]
                        entry["creator"] = non_spase_info["creators"]
                    elif is_article:
                        entry["@type"] = "ScholarlyArticle"
                    relation.append(entry)
            else:
                for each in relational_records.keys():
                    # most basic entry into relation
                    entry = {"@id": each, "identifier": each, "url": each}
                    is_dataset, is_article, non_spase_info = verify_type(each)
                    if is_dataset:
                        entry["@type"] = "Dataset"
                        entry["name"] = relational_records[each]["name"]
                        entry["description"] = relational_records[each]["description"]
                        if "license" in relational_records[each].keys():
                            entry["license"] = relational_records[each]["license"]
                        entry["creator"] = relational_records[each]["creators"]
                    elif is_article:
                        entry["@type"] = "ScholarlyArticle"
                    relation.append(entry)
    else:
        relation = None
    return relation

def findMatch(contacts_list: dict, person: str, author_role: list, index: int, matching_contact: bool = None) -> tuple[dict, list]:
    """
    Attempts to find a match in the provided dictionary of contacts (with their roles)
    found in the SPASE record to the given person name. If a match is found, that role
    is added to corresponding entry in the given list of author roles, and, in the
    dictionary of contacts, the role value is replaced with the formatted person name.

    :param contacts_list: The dictionary containing the contacts found in the SPASE record as keys
                            and their roles as values.
    :param person: The string containing the name of the person you wish to find a match for.
    :param author_role: The list of author roles.
    :param index: The index of the matching entry in author_roles that should be adjusted.
    :param matching_contact: The string containing the contact from the contacts_list parameter
                                that matches the person parameter

    :returns: The updated versions of the given dictionary of contacts and list of author roles.
    """
    for contact in contacts_list.keys():
        if matching_contact is None:
            initial = None
            first_name, _, last_name = contact.rpartition(".")
            first_name, _, initial = first_name.partition(".")
            *_, first_name = first_name.rpartition("/")
            if len(first_name) == 1:
                first_name = first_name[0] + "."
            # Assumption: if first name initial, middle initial, and last name
            #   match = same person
            # remove <f"{first_name[0]}."> in the lines below if this assumption
            #   is no longer accurate
            # if no middle name
            if not initial:
                if (
                    (f"{first_name[0]}." in person)
                    or (first_name in person)
                ) and (last_name in person):
                    matching_contact = contact
            # if middle name is not initialized, check whole string
            elif len(initial) > 1:
                if (
                    (
                        (f"{first_name[0]}." in person)
                        or (first_name in person)
                    )
                    and (initial in person)
                    and (last_name in person)
                ):
                    matching_contact = contact
            else:
                if (
                    (
                        (f"{first_name[0]}." in person)
                        or (first_name in person)
                    )
                    and (f"{initial}." in person)
                    and (last_name in person)
                ):
                    matching_contact = contact
    # if match is found, add role to author_role and replace role with
    #   formatted person name in contacts_list
    if matching_contact is not None:
        if author_role[index] != contacts_list[matching_contact]:
            author_role[index] = [author_role[index]] + contacts_list[matching_contact]
        if not initial:
            contacts_list[matching_contact] = f"{last_name}, {first_name}"
        elif len(initial) > 1:
            contacts_list[matching_contact] = (
                f"{last_name}, {first_name} {initial}"
            )
        else:
            contacts_list[matching_contact] = (
                f"{last_name}, {first_name} {initial}."
            )
    return contacts_list, author_role

def add_contributors(contributors:list, backups:dict, role_list:dict) -> Union[dict, None]:
    """
    Searches the provided dictionary of non-author role contacts to find any that have a role
    included in the provided list of roles. If one is found, a dictionary entry is created for
    this person and is added to the list of contributors.

    :param contributors: The list that holds all contributors to be provided to DataCite.
    :param backups: The dictionary containing the contacts found in the SPASE record as keys
                            and their non-author roles as values.
    :param role_list: The list of roles we want to find.

    :returns: The updated version of the given dictionary of contributors.
    """
    individual = {}
    first_contrib = True
    if contributors:
        first_contrib = False
    # search for roles in backups that match those in given list of roles
    for DC_Role, roles in role_list.items():
        keys = []
        for key, vals in backups.items():
            for val in vals:
                if val in roles:
                    #if key not in keys:
                    keys.append(key)
        if keys != []:
            for key in keys:
                # add call to get ORCiD and affiliation
                personStr, givenName, familyName = name_splitter(key)
                orcidID, affiliation, ror = get_ORCiD_and_Affiliation(key)
                #if ror == "":
                    #ror = get_ROR(affiliation)
                #print(f"{key} is being added to the contributors list")
                individual = person_format("contributor", DC_Role, personStr, givenName, familyName, affiliation, orcidID, ror, first_contrib)
                contributors.append(individual)
    return contributors