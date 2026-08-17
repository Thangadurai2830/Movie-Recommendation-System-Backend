#!/usr/bin/env python
"""
Comprehensive test runner for the Movie Recommendation System

This script runs all tests with coverage reporting and performance metrics.
Usage:
    python run_tests.py [options]
    
Options:
    --coverage      Generate coverage report
    --performance   Run performance tests
    --integration   Run integration tests
    --unit          Run unit tests only
    --verbose       Verbose output
    --failfast      Stop on first failure
    --parallel      Run tests in parallel
    --html-cov      Generate HTML coverage report
"""

import os
import sys
import django
import argparse
import subprocess
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')

def setup_django():
    """Setup Django for testing"""
    django.setup()

def run_command(command, capture_output=False):
    """Run a shell command"""
    print(f"Running: {' '.join(command)}")
    
    if capture_output:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        return subprocess.run(command).returncode

def install_test_dependencies():
    """Install test dependencies if not already installed"""
    dependencies = [
        'coverage>=7.0.0',
        'pytest>=7.0.0',
        'pytest-django>=4.5.0',
        'pytest-cov>=4.0.0',
        'pytest-xdist>=3.0.0',  # For parallel testing
        'factory-boy>=3.2.0',   # For test data factories
        'freezegun>=1.2.0',     # For time mocking
        'responses>=0.22.0',    # For HTTP mocking
    ]
    
    print("Checking test dependencies...")
    
    for dep in dependencies:
        try:
            __import__(dep.split('>=')[0].replace('-', '_'))
        except ImportError:
            print(f"Installing {dep}...")
            run_command([sys.executable, '-m', 'pip', 'install', dep])

def run_django_tests(args):
    """Run Django tests using manage.py test"""
    command = [sys.executable, 'manage.py', 'test']
    
    # Add test discovery patterns
    test_patterns = []
    
    if args.unit:
        test_patterns.extend([
            'recommendations.tests.test_models',
            'recommendations.tests.test_views',
            'recommendations.tests.test_ml_engine',
            'recommendations.tests.test_cache_utils',
        ])
    elif args.integration:
        test_patterns.extend([
            'recommendations.tests.test_tasks',
            'recommendations.tests.test_integration',
        ])
    else:
        test_patterns.append('recommendations.tests')
    
    command.extend(test_patterns)
    
    # Add Django test options
    if args.verbose:
        command.append('--verbosity=2')
    
    if args.failfast:
        command.append('--failfast')
    
    if args.parallel:
        command.extend(['--parallel', 'auto'])
    
    # Add coverage if requested
    if args.coverage:
        # Use coverage.py with Django
        coverage_command = [
            'coverage', 'run', '--source=.', '--omit=*/migrations/*,*/venv/*,*/env/*,manage.py,*/settings/*,*/tests/*'
        ]
        coverage_command.extend(command)
        command = coverage_command
    
    return run_command(command)

def run_pytest_tests(args):
    """Run tests using pytest"""
    command = ['pytest']
    
    # Add test discovery patterns
    if args.unit:
        command.extend([
            'recommendations/tests/test_models.py',
            'recommendations/tests/test_views.py',
            'recommendations/tests/test_ml_engine.py',
            'recommendations/tests/test_cache_utils.py',
        ])
    elif args.integration:
        command.extend([
            'recommendations/tests/test_tasks.py',
        ])
    else:
        command.append('recommendations/tests/')
    
    # Add pytest options
    if args.verbose:
        command.append('-v')
    
    if args.failfast:
        command.append('-x')
    
    if args.parallel:
        command.extend(['-n', 'auto'])
    
    # Add coverage if requested
    if args.coverage:
        command.extend([
            '--cov=recommendations',
            '--cov=movies',
            '--cov-report=term-missing',
        ])
        
        if args.html_cov:
            command.append('--cov-report=html')
    
    # Add performance tests if requested
    if args.performance:
        command.extend(['-m', 'performance'])
    
    return run_command(command)

def generate_coverage_report(args):
    """Generate coverage reports"""
    if not args.coverage:
        return
    
    print("\nGenerating coverage reports...")
    
    # Generate terminal report
    run_command(['coverage', 'report', '--show-missing'])
    
    # Generate HTML report if requested
    if args.html_cov:
        run_command(['coverage', 'html'])
        print("HTML coverage report generated in htmlcov/")
    
    # Generate XML report for CI/CD
    run_command(['coverage', 'xml'])
    print("XML coverage report generated as coverage.xml")

def run_linting():
    """Run code linting"""
    print("\nRunning code linting...")
    
    # Run flake8 if available
    try:
        return_code = run_command(['flake8', 'recommendations/', '--max-line-length=88', '--extend-ignore=E203,W503'])
        if return_code == 0:
            print("✓ Flake8 linting passed")
        else:
            print("✗ Flake8 linting failed")
    except FileNotFoundError:
        print("Flake8 not found, skipping linting")
    
    # Run black if available
    try:
        return_code = run_command(['black', '--check', 'recommendations/'])
        if return_code == 0:
            print("✓ Black formatting check passed")
        else:
            print("✗ Black formatting check failed")
    except FileNotFoundError:
        print("Black not found, skipping format check")

def run_security_checks():
    """Run security checks"""
    print("\nRunning security checks...")
    
    # Run bandit if available
    try:
        return_code = run_command(['bandit', '-r', 'recommendations/', '-f', 'json', '-o', 'bandit-report.json'])
        if return_code == 0:
            print("✓ Bandit security check passed")
        else:
            print("✗ Bandit security check found issues")
    except FileNotFoundError:
        print("Bandit not found, skipping security check")
    
    # Run safety if available
    try:
        return_code = run_command(['safety', 'check', '--json', '--output', 'safety-report.json'])
        if return_code == 0:
            print("✓ Safety dependency check passed")
        else:
            print("✗ Safety dependency check found vulnerabilities")
    except FileNotFoundError:
        print("Safety not found, skipping dependency check")

def run_performance_tests():
    """Run performance benchmarks"""
    print("\nRunning performance tests...")
    
    # This would run specific performance tests
    # For now, we'll just run the regular tests with performance markers
    command = [
        'pytest',
        'recommendations/tests/',
        '-m', 'performance',
        '--benchmark-only',
        '--benchmark-sort=mean',
        '--benchmark-json=benchmark-results.json'
    ]
    
    try:
        return run_command(command)
    except FileNotFoundError:
        print("pytest-benchmark not found, skipping performance tests")
        return 0

def check_test_database():
    """Check if test database can be created"""
    print("Checking test database setup...")
    
    try:
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'check', '--database', 'default'])
        print("✓ Database configuration is valid")
        return True
    except Exception as e:
        print(f"✗ Database configuration error: {e}")
        return False

def run_migration_tests():
    """Test database migrations"""
    print("\nTesting database migrations...")
    
    try:
        # Test migrations in a temporary database
        return_code = run_command([
            sys.executable, 'manage.py', 'migrate', '--run-syncdb', '--verbosity=0'
        ])
        
        if return_code == 0:
            print("✓ Database migrations successful")
        else:
            print("✗ Database migrations failed")
        
        return return_code == 0
    except Exception as e:
        print(f"✗ Migration test error: {e}")
        return False

def generate_test_report(results):
    """Generate a comprehensive test report"""
    print("\n" + "="*60)
    print("TEST REPORT SUMMARY")
    print("="*60)
    
    total_tests = sum(results.values())
    passed_tests = results.get('passed', 0)
    failed_tests = results.get('failed', 0)
    
    print(f"Total Tests Run: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n❌ {failed_tests} test(s) failed")
    
    # Additional metrics
    if os.path.exists('coverage.xml'):
        print("\n📊 Coverage report: coverage.xml")
    
    if os.path.exists('htmlcov/index.html'):
        print("📊 HTML coverage: htmlcov/index.html")
    
    if os.path.exists('benchmark-results.json'):
        print("⚡ Performance results: benchmark-results.json")
    
    print("\n" + "="*60)

def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='Run Movie Recommendation System tests')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--integration', action='store_true', help='Run integration tests')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--failfast', action='store_true', help='Stop on first failure')
    parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    parser.add_argument('--html-cov', action='store_true', help='Generate HTML coverage report')
    parser.add_argument('--lint', action='store_true', help='Run code linting')
    parser.add_argument('--security', action='store_true', help='Run security checks')
    parser.add_argument('--migrations', action='store_true', help='Test database migrations')
    parser.add_argument('--pytest', action='store_true', help='Use pytest instead of Django test runner')
    parser.add_argument('--install-deps', action='store_true', help='Install test dependencies')
    
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        install_test_dependencies()
    
    # Setup Django
    setup_django()
    
    # Check database setup
    if not check_test_database():
        print("Database setup failed. Please check your configuration.")
        return 1
    
    # Test migrations if requested
    if args.migrations:
        if not run_migration_tests():
            return 1
    
    # Run linting if requested
    if args.lint:
        run_linting()
    
    # Run security checks if requested
    if args.security:
        run_security_checks()
    
    # Run the main tests
    print("\nRunning tests...")
    
    if args.pytest:
        test_result = run_pytest_tests(args)
    else:
        test_result = run_django_tests(args)
    
    # Generate coverage report
    if args.coverage:
        generate_coverage_report(args)
    
    # Run performance tests if requested
    if args.performance:
        perf_result = run_performance_tests()
    
    # Generate final report
    results = {
        'passed': 0 if test_result != 0 else 1,
        'failed': 1 if test_result != 0 else 0,
    }
    
    generate_test_report(results)
    
    return test_result

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)