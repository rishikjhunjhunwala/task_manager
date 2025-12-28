#!/usr/bin/env python
"""
Phase 6A Verification Script

Run this script to verify template tags and context processors are working.

Usage:
    python manage.py shell < tests/test_phase6a.py
    
    OR run interactively:
    python manage.py shell
    >>> exec(open('tests/test_phase6a.py').read())
"""

import sys
from datetime import timedelta

print("=" * 60)
print("Phase 6A Verification: Template Tags & Context Processors")
print("=" * 60)

# Track test results
tests_passed = 0
tests_failed = 0

def test_pass(name):
    global tests_passed
    tests_passed += 1
    print(f"✓ PASS: {name}")

def test_fail(name, error=""):
    global tests_failed
    tests_failed += 1
    print(f"✗ FAIL: {name}")
    if error:
        print(f"  Error: {error}")


# =============================================================================
# Test 1: Template Tag Module Import
# =============================================================================
print("\n--- Test 1: Template Tag Module Import ---")

try:
    from apps.tasks.templatetags import task_tags
    test_pass("task_tags module imports successfully")
except ImportError as e:
    test_fail("task_tags module import", str(e))


# =============================================================================
# Test 2: Filter Functions Exist
# =============================================================================
print("\n--- Test 2: Filter Functions Exist ---")

required_filters = [
    'is_overdue',
    'is_escalated',
    'hours_overdue',
    'hours_overdue_display',
    'format_deadline',
    'deadline_short',
    'status_class',
    'priority_class',
    'task_row_class',
    'task_card_class',
    'status_display',
    'priority_display',
    'can_edit',
    'can_change_status',
    'escalation_level',
    'next_status',
    'next_status_display',
]

for filter_name in required_filters:
    if hasattr(task_tags, filter_name):
        test_pass(f"Filter '{filter_name}' exists")
    else:
        test_fail(f"Filter '{filter_name}' missing")


# =============================================================================
# Test 3: Simple Tag Functions Exist
# =============================================================================
print("\n--- Test 3: Simple Tag Functions Exist ---")

required_tags = [
    'overdue_badge',
    'priority_badge',
    'status_badge',
    'task_type_badge',
    'deadline_display',
]

for tag_name in required_tags:
    if hasattr(task_tags, tag_name):
        test_pass(f"Tag '{tag_name}' exists")
    else:
        test_fail(f"Tag '{tag_name}' missing")


# =============================================================================
# Test 4: Status Class Filter
# =============================================================================
print("\n--- Test 4: Status Class Filter ---")

status_tests = [
    ('pending', 'status-pending'),
    ('in_progress', 'status-in-progress'),
    ('completed', 'status-completed'),
    ('verified', 'status-verified'),
    ('cancelled', 'status-cancelled'),
]

for status, expected_class in status_tests:
    result = task_tags.status_class(status)
    if result == expected_class:
        test_pass(f"status_class('{status}') = '{expected_class}'")
    else:
        test_fail(f"status_class('{status}')", f"Expected '{expected_class}', got '{result}'")


# =============================================================================
# Test 5: Priority Class Filter
# =============================================================================
print("\n--- Test 5: Priority Class Filter ---")

priority_tests = [
    ('low', 'priority-low'),
    ('medium', 'priority-medium'),
    ('high', 'priority-high'),
    ('critical', 'priority-critical'),
]

for priority, expected_class in priority_tests:
    result = task_tags.priority_class(priority)
    if result == expected_class:
        test_pass(f"priority_class('{priority}') = '{expected_class}'")
    else:
        test_fail(f"priority_class('{priority}')", f"Expected '{expected_class}', got '{result}'")


# =============================================================================
# Test 6: Format Deadline Filter
# =============================================================================
print("\n--- Test 6: Format Deadline Filter ---")

from django.utils import timezone

now = timezone.now()

# Test today
today_deadline = now.replace(hour=17, minute=0, second=0, microsecond=0)
result = task_tags.format_deadline(today_deadline)
if "Today" in result:
    test_pass(f"format_deadline for today includes 'Today'")
else:
    test_fail(f"format_deadline for today", f"Expected 'Today' in result, got '{result}'")

# Test tomorrow
tomorrow_deadline = now + timedelta(days=1)
result = task_tags.format_deadline(tomorrow_deadline)
if "Tomorrow" in result:
    test_pass(f"format_deadline for tomorrow includes 'Tomorrow'")
else:
    test_fail(f"format_deadline for tomorrow", f"Expected 'Tomorrow' in result, got '{result}'")

# Test overdue (yesterday)
yesterday_deadline = now - timedelta(days=1)
result = task_tags.format_deadline(yesterday_deadline)
if "Yesterday" in result or "ago" in result:
    test_pass(f"format_deadline for yesterday shows past")
else:
    test_fail(f"format_deadline for yesterday", f"Expected past indicator, got '{result}'")

# Test None
result = task_tags.format_deadline(None)
if result == "No deadline":
    test_pass("format_deadline(None) = 'No deadline'")
else:
    test_fail("format_deadline(None)", f"Expected 'No deadline', got '{result}'")


# =============================================================================
# Test 7: Context Processor Import
# =============================================================================
print("\n--- Test 7: Context Processor Import ---")

try:
    from apps.tasks.context_processors import task_counts, user_permissions
    test_pass("Context processors import successfully")
except ImportError as e:
    test_fail("Context processors import", str(e))


# =============================================================================
# Test 8: Context Processor with Anonymous User
# =============================================================================
print("\n--- Test 8: Context Processor with Anonymous User ---")

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

factory = RequestFactory()
request = factory.get('/')
request.user = AnonymousUser()

context = task_counts(request)

expected_keys = [
    'pending_task_count',
    'overdue_task_count',
    'my_tasks_count',
    'assigned_to_me_count',
    'i_assigned_count',
]

for key in expected_keys:
    if key in context and context[key] == 0:
        test_pass(f"Anonymous user: {key} = 0")
    else:
        test_fail(f"Anonymous user: {key}", f"Expected 0, got {context.get(key, 'missing')}")


# =============================================================================
# Test 9: Context Processor with Authenticated User
# =============================================================================
print("\n--- Test 9: Context Processor with Authenticated User ---")

from django.contrib.auth import get_user_model
User = get_user_model()

try:
    user = User.objects.first()
    if user:
        request = factory.get('/')
        request.user = user
        
        context = task_counts(request)
        
        # Check all required keys exist
        for key in expected_keys:
            if key in context:
                test_pass(f"Authenticated user: {key} exists (value: {context[key]})")
            else:
                test_fail(f"Authenticated user: {key} missing")
    else:
        print("  SKIP: No users in database - create a user to test")
except Exception as e:
    test_fail("Context processor with authenticated user", str(e))


# =============================================================================
# Test 10: User Permissions Context Processor
# =============================================================================
print("\n--- Test 10: User Permissions Context Processor ---")

context = user_permissions(request)

permission_keys = [
    'can_manage_users',
    'can_view_all_tasks',
    'can_view_department_tasks',
    'can_view_activity_log',
    'can_view_reports',
    'is_admin',
    'is_senior_manager',
    'is_manager',
]

for key in permission_keys:
    if key in context:
        test_pass(f"Permission flag '{key}' exists")
    else:
        test_fail(f"Permission flag '{key}' missing")


# =============================================================================
# Test 11: Template Loading
# =============================================================================
print("\n--- Test 11: Template Tag Loading in Django Template ---")

from django.template import Template, Context, TemplateSyntaxError

try:
    # Test loading task_tags
    template = Template('{% load task_tags %}{{ status|status_class }}')
    context = Context({'status': 'pending'})
    result = template.render(context)
    
    if result.strip() == 'status-pending':
        test_pass("Template tag loads and works in Django template")
    else:
        test_fail("Template tag in Django template", f"Expected 'status-pending', got '{result}'")
except TemplateSyntaxError as e:
    test_fail("Template tag loading", str(e))


# =============================================================================
# Test 12: Simple Tag Output
# =============================================================================
print("\n--- Test 12: Simple Tag HTML Output ---")

try:
    # Create a mock task-like object
    class MockTask:
        priority = 'high'
        status = 'pending'
        task_type = 'delegated'
        deadline = None
        escalated_to_sm2_at = None
        escalated_to_sm1_at = None
    
    mock_task = MockTask()
    
    # Test priority badge
    result = task_tags.priority_badge(mock_task)
    if 'High' in str(result) and '<span' in str(result):
        test_pass("priority_badge returns HTML with label")
    else:
        test_fail("priority_badge HTML output", f"Unexpected output: {result}")
    
    # Test status badge  
    result = task_tags.status_badge(mock_task)
    if 'Pending' in str(result) and '<span' in str(result):
        test_pass("status_badge returns HTML with label")
    else:
        test_fail("status_badge HTML output", f"Unexpected output: {result}")
        
except Exception as e:
    test_fail("Simple tag HTML output", str(e))


# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 60)
print(f"SUMMARY: {tests_passed} passed, {tests_failed} failed")
print("=" * 60)

if tests_failed == 0:
    print("\n✓ All Phase 6A tests passed! Ready for Phase 6B.")
else:
    print(f"\n✗ {tests_failed} test(s) failed. Please fix issues before proceeding.")
