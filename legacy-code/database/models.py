from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Date, 
    ForeignKey, Text, Index, DateTime, Enum
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from utils.id_generator import generate_short_id

Base = declarative_base()

class ProjectParticulars(Base):
    """Main table for planning application data
    
    Attributes:
        reference_id (str): Unique identifier for the project
        site_address (str): Full address of the site
        proposal (str): Description of the proposed development
        ...
    
    Relationships:
        dates (ProjectDates): One-to-one relationship with dates
        misc_data (ProjectMiscellaneous): One-to-one relationship with miscellaneous data
        ...
    """
    __tablename__ = 'project_particulars'
    
    # Primary key
    reference_id = Column(String(50), primary_key=True, default=lambda: generate_short_id())
    
    # Required fields
    site_address = Column(String(500), nullable=False)
    proposal = Column(String(10000), nullable=False)
    
    # Core fields
    council_name = Column(String(100))
    application_reference = Column(String(50))
    status = Column(String(100))
    decision = Column(String(100))
    
    # Address components
    site_address_line1 = Column(String(255))
    site_address_line2 = Column(String(255))
    site_address_town = Column(String(100))
    site_address_city = Column(String(100))
    site_address_county = Column(String(100))
    site_address_country = Column(String(100))
    site_address_postcode = Column(String(20))
    
    # Project details
    residential_units = Column(Float)
    commercial_units = Column(Float)
    estimated_value = Column(String(50))
    householder_type = Column(String(100))
    proposal_category = Column(String(100))
    proposal_is_householder = Column(Boolean)
    proposal_is_conversion = Column(Boolean)
    proposal_conversion_type = Column(String(100))
    
    # Administrative fields
    parish = Column(String(100))
    ward = Column(String(100))
    application_url = Column(String(500))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    dates = relationship("ProjectDates", back_populates="project", uselist=False, cascade="all, delete-orphan")
    misc_data = relationship("ProjectMiscellaneous", back_populates="project", uselist=False, cascade="all, delete-orphan")
    applicant = relationship("ApplicantDetails", back_populates="project", uselist=False, cascade="all, delete-orphan")
    agent = relationship("AgentDetails", back_populates="project", uselist=False, cascade="all, delete-orphan")
    architect = relationship("ArchitectDetails", back_populates="project", uselist=False, cascade="all, delete-orphan")
    companies = relationship("CompanyDetails", back_populates="project", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_app_reference', 'application_reference'),
        Index('idx_site_address', 'site_address'),
        Index('idx_status', 'status'),
        Index('idx_council', 'council_name'),
        Index('idx_postcode', 'site_address_postcode'),
        Index('idx_created', 'created_at'),
        Index('idx_updated', 'updated_at'),
        Index('idx_council_status', 'council_name', 'status'),
        Index('idx_date_status', 'created_at', 'status'),
        Index('idx_active_proposals', 'status', postgresql_where=(status != 'INVALID')),
    )

class ProjectDates(Base):
    """Table for all date-related fields"""
    __tablename__ = 'project_dates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(50), ForeignKey('project_particulars.reference_id', ondelete="CASCADE"), nullable=False)
    
    valid_from = Column(Date)
    registration_date = Column(Date)
    decision_date = Column(Date)
    expiry_date = Column(Date)
    consultation_start_date = Column(Date)
    consultation_expiry_date = Column(Date)
    target_decision_date = Column(Date)
    statutory_expiry_date = Column(Date)
    dispatch_date = Column(Date)
    decision_due_date = Column(Date)
    decision_expiry_date = Column(Date)
    site_notice_date = Column(Date)
    publicity_end_date = Column(Date)
    
    # Add missing date fields
    advert_expiry_date = Column(Date)
    extended_target_decision_date = Column(Date)
    committee_date = Column(Date)
    received_date = Column(Date)
    site_visit_date = Column(Date)
    planning_perfromance_agreement_due_date = Column(Date)  # Note: typo in CSV 'perfromance'
    actual_committee_date = Column(Date)
    appeal_external_decision_date = Column(Date)
    final_grant_date = Column(Date)
    extension_date = Column(Date)
    appeal_lodged_date = Column(Date)
    appeal_notify_date = Column(Date)
    submision_expiry_date = Column(Date)  # Note: typo in field name 'submision'
    application_date = Column(Date)
    press_notice_start_date = Column(Date)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationship
    project = relationship("ProjectParticulars", back_populates="dates")
    
    # Indexes
    __table_args__ = (
        Index('idx_dates_registration', 'registration_date'),
        Index('idx_dates_decision', 'decision_date'),
        Index('idx_dates_consultation', 'consultation_start_date', 'consultation_expiry_date'),
    )

class ProjectMiscellaneous(Base):
    """Table for miscellaneous project data"""
    __tablename__ = 'project_miscellaneous'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(50), ForeignKey('project_particulars.reference_id', ondelete="CASCADE"), nullable=False)
    
    environmental_assessment_required = Column(String(50))
    case_officer_name = Column(String(100))
    determination_level = Column(String(100))
    development_type = Column(String(100))
    application_type = Column(String(100))
    application_type_id = Column(String(50))
    division = Column(String(100))
    existing_land_use = Column(String(100))
    proposed_land_use = Column(String(100))
    
    # Add missing fields
    location_coordinates = Column(String(255))
    expected_decision_level = Column(String(100))
    listed_building_grade = Column(String(50))
    extension_of_time = Column(Boolean)
    planning_performance_agreement = Column(Boolean)
    appeal_reference = Column(String(100))
    easting = Column(Float)
    northing = Column(Float)
    appeal_type = Column(String(100))
    development_category = Column(String(100))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationship
    project = relationship("ProjectParticulars", back_populates="misc_data")
    
    # Indexes
    __table_args__ = (
        Index('idx_misc_apptype', 'application_type'),
        Index('idx_misc_development', 'development_type'),
        Index('idx_misc_caseofficer', 'case_officer_name'),
    )

class CompanyDetails(Base):
    """Table for company details"""
    __tablename__ = 'company_details'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(50), ForeignKey('project_particulars.reference_id', ondelete="CASCADE"), nullable=False)
    company_type = Column(String(20), nullable=False)  # 'agent' or 'applicant'
    
    # Company information
    company_name = Column(String(255))
    company_reg_name = Column(String(255))
    company_reg_number = Column(String(50))
    company_reg_address_line1 = Column(String(255))
    company_reg_address_line2 = Column(String(255))
    company_reg_city = Column(String(100))
    company_reg_county = Column(String(100))
    company_reg_country = Column(String(100))
    company_reg_postcode = Column(String(20))
    company_reg_type = Column(String(100))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    project = relationship("ProjectParticulars", back_populates="companies")
    agent = relationship("AgentDetails", back_populates="company", uselist=False)
    applicant = relationship("ApplicantDetails", back_populates="company", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_company_name', 'company_name'),
        Index('idx_company_reg', 'company_reg_number'),
        Index('idx_company_type', 'company_type'),
    )

class ApplicantDetails(Base):
    """Table for applicant details"""
    __tablename__ = 'applicant_details'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(50), ForeignKey('project_particulars.reference_id', ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey('company_details.id', ondelete="SET NULL"), nullable=True)
    
    # Personal details
    name_first = Column(String(100))
    name_middle = Column(String(100))
    name_last = Column(String(100))
    name_title = Column(String(20))
    name_suffix = Column(String(20))
    name_gender = Column(String(20))
    name_salutation = Column(String(50))
    
    # Contact details
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    address_town = Column(String(100))
    address_city = Column(String(100))
    address_county = Column(String(100))
    address_country = Column(String(100))
    address_postcode = Column(String(20))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    project = relationship("ProjectParticulars", back_populates="applicant")
    company = relationship("CompanyDetails", back_populates="applicant")
    
    # Indexes
    __table_args__ = (
        Index('idx_applicant_name', 'name_last', 'name_first'),
    )

    # Add missing fields
    applicant_surname = Column(String(100))  # This might be redundant with name_last

class AgentDetails(Base):
    """Table for agent details"""
    __tablename__ = 'agent_details'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(50), ForeignKey('project_particulars.reference_id', ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey('company_details.id', ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    
    # Personal details
    name_first = Column(String(100))
    name_middle = Column(String(100))
    name_last = Column(String(100))
    name_title = Column(String(20))
    name_suffix = Column(String(20))
    name_gender = Column(String(20))
    name_salutation = Column(String(50))
    
    # Contact details
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    address_town = Column(String(100))
    address_city = Column(String(100))
    address_county = Column(String(100))
    address_country = Column(String(100))
    address_postcode = Column(String(20))
    phone = Column(String(50))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    project = relationship("ProjectParticulars", back_populates="agent")
    company = relationship("CompanyDetails", back_populates="agent")
    
    # Indexes
    __table_args__ = (
        Index('idx_agent_name', 'name_last', 'name_first'),
    )

    # Add missing fields
    agent_initials = Column(String(20))
    agent_title = Column(String(20))  # This might be redundant with name_title

class ArchitectDetails(Base):
    """Table for architect details (for future use)"""
    __tablename__ = 'architect_details'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(50), ForeignKey('project_particulars.reference_id', ondelete="CASCADE"), nullable=False)
    
    # Personal details
    name_first = Column(String(100))
    name_last = Column(String(100))
    registration_number = Column(String(50))  # Professional registration number
    practice_name = Column(String(255))
    
    # Contact details
    email = Column(String(255))
    phone = Column(String(50))
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    address_city = Column(String(100))
    address_postcode = Column(String(20))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationship
    project = relationship("ProjectParticulars", back_populates="architect")
    
    # Indexes
    __table_args__ = (
        Index('idx_architect_name', 'name_last', 'name_first'),
        Index('idx_architect_practice', 'practice_name'),
    ) 