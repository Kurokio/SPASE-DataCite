# SPASE-DataCite Mapping

> This project aims to aid in creating/updating the DataCite DOI Metadata Records for SPASE datasets.

This project consists of some scripts and a Jupyter notebook which perform the following:
- scrapes SPASE records provided by user for rich metadata to be populated within its associated DataCite metadata record
- converts this extracted SPASE metadata into a JSON file formatted according to DataCite's metadata schema
- saves this JSON locally for user validation
- publishes this new/updated DataCite metadata record on the user's DataCite account, if desired

*Note that this project was tested in Spring/Summer 2025 on SPASE version 2.7.0*

## Installation Instructions
- Clone this repo.
```python
git clone https://github.com/Kurokio/SPASE-DataCite
```

## Usage
Follow the notebook "HowToUse" which walks you through step-by-step how to do the actions listed above.

## Contribution
Contributors and collaborators are welcome. Acceptable contributions can be documentation, code, suggesting ideas, and submitting issues and bugs.

While this was developed by NASA HDRL, this script can be used (and can benefit) any repository who uses SPASE to house their metadata. Some minor tweaks may be needed to fit your specific agency/community's guidelines/formatting, however. Please do not hesitate to reach out to the contact info provided below if you need assistance implementing this script for your needs.

Make sure to be nice when contributing and submitting commit messages.

## Credits
Thanks to the following people who helped with this project:
- <a href="https://github.com/rebeccaringuette" target="_blank">@rebeccaringuette</a>
- <a href="https://github.com/orgs/hpde/people/tressahelvey" target="_blank">@tressahelvey</a>
- <a href="https://github.com/orgs/hpde/people/andrkoval" target="_blank">@andrkoval
- <a href="https://github.com/orgs/hpde/people/catbyrd" target="_blank">@catbyrd

## Contact
Contact me via LinkedIn or by using the email on my ORCiD page.
Zach Boquet - <a href="https://www.linkedin.com/in/zach-boquet-62a996254/" target="_blank">LinkedIn</a> - <a href="https://orcid.org/0009-0005-1686-262X" target="_blank">ORCiD</a>
