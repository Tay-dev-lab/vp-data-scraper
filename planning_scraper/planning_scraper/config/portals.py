"""
Portal URL configuration for UK planning portals.

IDOX is the dominant framework (~55 councils).
URLs are organized by prefix/pattern for easier maintenance.
"""

from typing import List

# =============================================================================
# IDOX Portal URLs - PRODUCTION MODE
# =============================================================================

# URLs with "planning." prefix
IDOX_PLANNING = [
    # "https://planning.doncaster.gov.uk/online-applications/search.do?action=advanced",  # Already scraped
    "https://planning.fife.gov.uk/online/search.do?action=advanced",
    "https://planning.inverclyde.gov.uk/Online/search.do?action=advanced",
    "https://planning.brentwood.gov.uk/online-applications/search.do?action=advanced",
]

# URLs with "pa." prefix
IDOX_PA = [
    "https://pa.sevenoaks.gov.uk/online-applications/search.do?action=advanced",
    "https://pa.shropshire.gov.uk/online-applications/search.do?action=advanced",
]

# URLs with "planapp." prefix
IDOX_PLANAPP = [
    "https://planapp.knowsley.gov.uk/online-applications/search.do?action=advanced",
]

# URLs with "publicaccess." prefix
IDOX_PUBLICACCESS = [
    "https://publicaccess.braintree.gov.uk/online-applications/search.do?action=advanced",
    # "https://publicaccess.chichester.gov.uk/online-applications/search.do?action=advanced",  # Already scraped
    "https://publicaccess.cotswold.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.cravendc.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.darlington.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.dartford.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.dover.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.eastherts.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.e-lindsey.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.east-northamptonshire.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.exeter.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.fdean.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.gloucester.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.gosport.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.guildford.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.hart.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.hastings.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.huntingdonshire.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.iow.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.kingston.gov.uk/online-applications/search.do?action=advanced",
    # "https://publicaccess.leeds.gov.uk/online-applications/search.do?action=advanced",  # Already scraped
    "https://publicaccess.maldon.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.mendip.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.newark-sherwooddc.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.newcastle-staffs.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.northumberland.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.nottinghamcity.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.rushmoor.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.rutland.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.solihull.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.southribble.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.southsomerset.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.spelthorne.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.sthelens.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.stevenage.gov.uk/online-applications/search.do?action=advanced&searchType=Application",
    "https://publicaccess.stroud.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.surreyheath.gov.uk/online-applications/search.do?action=advanced",
    "https://publicaccess.clacks.gov.uk/publicaccess/search.do?action=advanced",
    "https://publicaccess.brentwood.gov.uk/online-applications/search.do?action=advanced",
]

# URLs with "planningpublicaccess." prefix
IDOX_PLANNING_PUBLICACCESS = [
    "https://planningpublicaccess.southdowns.gov.uk/online-applications/search.do?action=advanced",
    "https://planningpublicaccess.southampton.gov.uk/online-applications/search.do?action=advanced",
]

# URLs with special prefixes
IDOX_SPECIAL = [
    "https://www.eplanningcnpa.co.uk/online-applications/search.do?action=advanced",
    "https://idoxpa.westminster.gov.uk/online-applications/search.do?action=advanced",
    "https://development.towerhamlets.gov.uk/online-applications/search.do?action=advanced",
    "https://searchapplications.bromley.gov.uk/online-applications/search.do?action=advanced",
    "https://planning-applications.midlothian.gov.uk/OnlinePlanning/search.do?action=advanced",
    "https://boppa.poole.gov.uk/online-applications/search.do?action=advanced",
    "https://regs.thurrock.gov.uk/online-applications/search.do?action=advanced",
]

# Combined list of all active IDOX URLs
IDOX_URLS: List[str] = (
    IDOX_PLANNING
    + IDOX_PA
    + IDOX_PLANAPP
    + IDOX_PUBLICACCESS
    + IDOX_PLANNING_PUBLICACCESS
    + IDOX_SPECIAL
)


def get_active_idox_urls() -> List[str]:
    """Return list of active IDOX URLs for scraping."""
    return IDOX_URLS.copy()


# =============================================================================
# Already Scraped URLs (for reference)
# =============================================================================
# IDOX_ALREADY_SCRAPED = [
#     "https://planning.doncaster.gov.uk/online-applications/search.do?action=advanced",
#     "https://publicaccess.chichester.gov.uk/online-applications/search.do?action=advanced",
#     "https://publicaccess.leeds.gov.uk/online-applications/search.do?action=advanced",
# ]


# =============================================================================
# Other Framework URLs (for future phases)
# =============================================================================

# Agile Applications URLs
AGILE_URLS = [
    "https://planning.agileapplications.co.uk/cannock/search-applications/",
    "https://planning.agileapplications.co.uk/exmoor/search-applications/",
    "https://planning.agileapplications.co.uk/ldnpa/search-applications/",
    "https://planning.agileapplications.co.uk/middlesbrough/search-applications/",
    "https://planning.agileapplications.co.uk/mole/search-applications/",
    "https://planning.agileapplications.co.uk/nfnpa/search-applications/",
    "https://planning.agileapplications.co.uk/rugby/search-applications/",
    "https://planning.agileapplications.co.uk/slough/search-applications/",
    "https://planning.agileapplications.co.uk/snowdonia/search-applications/",
    "https://planning.agileapplications.co.uk/tmbc/search-applications/",
    "https://planning.agileapplications.co.uk/pembrokeshire/search-applications/",
    "https://planning.agileapplications.co.uk/flintshire/search-applications/",
    "https://planning.agileapplications.co.uk/islington/search-applications/",
    "https://planning.agileapplications.co.uk/pcnpa/search-applications/",
    "https://planning.agileapplications.co.uk/yorkshiredales/search-applications/",
]

# ASPX/Northgate URLs
ASPX_URLS = [
    "https://planning.blackburn.gov.uk/Northgate/PlanningExplorer/GeneralSearch.aspx",
    "https://planningrecords.camden.gov.uk/NECSWS/PlanningExplorer/GeneralSearch.aspx",
    "https://www.eaststaffsbc.gov.uk/Northgate/PlanningExplorer/GeneralSearch.aspx",
    "https://planning.merton.gov.uk/Northgate/PlanningExplorerAA/GeneralSearch.aspx",
    "https://planning.tamworth.gov.uk/northgate/planningexplorer/generalsearch.aspx",
    "https://planning.wandsworth.gov.uk/Northgate/PlanningExplorer/GeneralSearch.aspx",
]

# OCELLA URLs
OCELLA_URLS = [
    "https://development.havering.gov.uk/OcellaWeb/planningSearch",
]

# ARCUS/Salesforce URLs
ARCUS_URLS = [
    "https://eppingforestdc.my.site.com/pr/s/sfsites/aura",
]
