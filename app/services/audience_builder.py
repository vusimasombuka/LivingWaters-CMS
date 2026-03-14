from app.models.member import Member
from app.models.visitor import Visitor  # Added import
from app.models.lookup import Lookup
from app.utils import normalize_sa_phone
from datetime import datetime, date
from sqlalchemy import func, and_, or_
from app.extensions import db

class AudienceBuilder:
    """Builds dynamic audience queries based on filters"""
    
    @staticmethod
    def get_available_filters():
        """Returns filter configuration for UI"""
        departments = Lookup.query.filter_by(category="department").all()
        marital_statuses = Lookup.query.filter_by(category="marital_status").all()
        member_statuses = Lookup.query.filter_by(category="member_status").all()
        
        return {
            'audience_type': {
                'type': 'select',
                'label': 'Target Audience',
                'required': True,
                'options': [
                    {'value': 'members', 'label': 'All Members'},
                    {'value': 'visitors', 'label': 'All Visitors'},
                    {'value': 'all', 'label': 'Everyone (Members & Visitors)'}
                ],
                'default': 'members'
            },
            'gender': {
                'type': 'multi_select',
                'label': 'Gender (Members only)',
                'applies_to': ['members'],
                'options': [
                    {'value': 'male', 'label': 'Male'},
                    {'value': 'female', 'label': 'Female'}
                ]
            },
            'marital_status': {
                'type': 'multi_select',
                'label': 'Marital Status (Members only)',
                'applies_to': ['members'],
                'options': [{'value': s.value, 'label': s.value} for s in marital_statuses]
            },
            'department': {
                'type': 'multi_select',
                'label': 'Department (Members only)',
                'applies_to': ['members'],
                'options': [{'value': d.value, 'label': d.value} for d in departments]
            },
            'baptized': {
                'type': 'boolean',
                'label': 'Baptized (Members only)',
                'applies_to': ['members']
            },
            'membership_course': {
                'type': 'boolean',
                'label': 'Completed Membership Course (Members only)',
                'applies_to': ['members']
            },
            'member_status': {
                'type': 'multi_select',
                'label': 'Member Status (Members only)',
                'applies_to': ['members'],
                'options': [{'value': s.value, 'label': s.value} for s in member_statuses]
            },
            'age_range': {
                'type': 'range',
                'label': 'Age Range (Members only)',
                'applies_to': ['members'],
                'min': 0,
                'max': 100
            }
        }
    
    @staticmethod
    def build_query(filters, branch_id=None, require_phone=True, audience_type='members'):
        """
        Builds query based on filter criteria
        
        Args:
            filters: dict of filter criteria
            branch_id: branch to filter by
            require_phone: only include records with phone numbers
            audience_type: 'members' or 'visitors' (returns Query object)
                          Note: Use get_recipients() for 'all' instead
        """
        if audience_type == 'members':
            return AudienceBuilder._build_member_query(filters, branch_id, require_phone)
        elif audience_type == 'visitors':
            return AudienceBuilder._build_visitor_query(filters, branch_id, require_phone)
        else:
            raise ValueError("Use get_recipients() or get_count() for audience_type='all'")
    
    @staticmethod
    def _build_member_query(filters, branch_id, require_phone):
        """Build query for Members with full filtering"""
        query = Member.query
        
        if branch_id:
            query = query.filter(Member.branch_id == branch_id)
        
        if require_phone:
            query = query.filter(
                Member.phone != None,
                Member.phone != ''
            )
        
        if not filters:
            return query
        
        # Apply member-specific filters
        if filters.get('gender'):
            query = query.filter(Member.gender.in_(filters['gender']))
        
        if filters.get('marital_status'):
            query = query.filter(Member.marital_status.in_(filters['marital_status']))
        
        if filters.get('department'):
            query = query.filter(Member.department.in_(filters['department']))
        
        if filters.get('baptized') is not None:
            query = query.filter(Member.baptized == filters['baptized'])
        
        if filters.get('membership_course') is not None:
            query = query.filter(Member.membership_course == filters['membership_course'])
        
        if filters.get('member_status'):
            query = query.filter(Member.member_status.in_(filters['member_status']))
        
        if filters.get('age_range'):
            min_age = filters['age_range'].get('min', 0)
            max_age = filters['age_range'].get('max', 100)
            
            today = date.today()
            min_date = today.replace(year=today.year - max_age - 1)
            max_date = today.replace(year=today.year - min_age)
            
            query = query.filter(
                Member.date_of_birth.between(min_date, max_date)
            )
        
        return query
    
    @staticmethod
    def _build_visitor_query(filters, branch_id, require_phone):
        """Build query for Visitors (basic filters only - visitors don't have departments/status fields)"""
        query = Visitor.query
        
        if branch_id:
            query = query.filter(Visitor.branch_id == branch_id)
        
        if require_phone:
            query = query.filter(
                Visitor.phone != None,
                Visitor.phone != ''
            )
        
        # Note: Visitors only support branch and phone filtering
        # Member-specific filters (department, baptized, etc.) are ignored for visitors
        
        return query
    
    @staticmethod
    def get_count(filters, branch_id=None, require_phone=True, audience_type='members'):
        """
        Get count of matching recipients.
        Supports audience_type='all' to get total of both members and visitors.
        """
        if audience_type == 'all':
            member_count = AudienceBuilder._build_member_query(filters, branch_id, require_phone).count()
            visitor_count = AudienceBuilder._build_visitor_query(filters, branch_id, require_phone).count()
            return member_count + visitor_count
        else:
            query = AudienceBuilder.build_query(filters, branch_id, require_phone, audience_type)
            return query.count()
    
    @staticmethod
    def get_recipients(filters, branch_id=None, require_phone=True, audience_type='members'):
        """
        Get all recipients as a list of objects.
        Supports audience_type='all' to get combined list of members and visitors.
        """
        if audience_type == 'all':
            members = AudienceBuilder._build_member_query(filters, branch_id, require_phone).all()
            visitors = AudienceBuilder._build_visitor_query(filters, branch_id, require_phone).all()
            return members + visitors
        else:
            query = AudienceBuilder.build_query(filters, branch_id, require_phone, audience_type)
            return query.all()
    
    @staticmethod
    def get_recipients_paginated(filters, page=1, per_page=50, branch_id=None, require_phone=True, audience_type='members'):
        """
        Get paginated list of recipients.
        For audience_type='all', pagination is done in-memory (suitable for typical church sizes).
        """
        if audience_type == 'all':
            # Fetch all and paginate in Python
            # Note: For very large databases (10k+ combined), consider implementing
            # a more efficient SQL UNION approach
            all_results = AudienceBuilder.get_recipients(filters, branch_id, require_phone, 'all')
            total = len(all_results)
            
            start = (page - 1) * per_page
            end = start + per_page
            items = all_results[start:end]
            
            # Create mock pagination object
            class MockPagination:
                def __init__(self, items, total, page, per_page):
                    self.items = items
                    self.total = total
                    self.page = page
                    self.per_page = per_page
                    self.pages = (total + per_page - 1) // per_page if per_page > 0 else 0
                    self.has_next = page < self.pages
                    self.has_prev = page > 1
                    self.next_num = page + 1 if self.has_next else None
                    self.prev_num = page - 1 if self.has_prev else None
                    
            return MockPagination(items, total, page, per_page)
        else:
            query = AudienceBuilder.build_query(filters, branch_id, require_phone, audience_type)
            return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def personalize_message(content, person):
        """
        Replace placeholders with person data.
        Works with both Member and Visitor objects.
        Supports both {{variable}} and {variable} formats.
        """
        # Determine format used
        uses_double_braces = '{{' in content
        
        if uses_double_braces:
            replacements = {
                '{{first_name}}': getattr(person, 'first_name', '') or '',
                '{{last_name}}': getattr(person, 'last_name', '') or '',
                '{{full_name}}': f"{getattr(person, 'first_name', '') or ''} {getattr(person, 'last_name', '') or ''}".strip(),
                '{{department}}': getattr(person, 'department', '') or '',
                '{{phone}}': getattr(person, 'phone', '') or ''
            }
        else:
            # Single brace format (used in your existing templates like "Hi {name}!")
            replacements = {
                '{name}': getattr(person, 'first_name', '') or '',
                '{first_name}': getattr(person, 'first_name', '') or '',
                '{last_name}': getattr(person, 'last_name', '') or '',
                '{full_name}': f"{getattr(person, 'first_name', '') or ''} {getattr(person, 'last_name', '') or ''}".strip(),
                '{department}': getattr(person, 'department', '') or '',
                '{phone}': getattr(person, 'phone', '') or ''
            }
        
        result = content
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result