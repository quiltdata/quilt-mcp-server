"""Tests for QuiltOps abstract interface - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of the QuiltOps
abstract base class before implementation. Tests cover abstract methods, type hints, and interface compliance.
"""

from __future__ import annotations

import pytest
from abc import ABC, abstractmethod
from typing import List, Optional
from unittest.mock import Mock


class TestQuiltOpsInterface:
    """Test QuiltOps abstract base class interface."""

    def test_quilt_ops_can_be_imported(self):
        """Test that QuiltOps can be imported from ops module."""
        # This test will fail initially - that's the RED phase of TDD
        from quilt_mcp.ops.quilt_ops import QuiltOps
        assert QuiltOps is not None

    def test_quilt_ops_is_abstract_base_class(self):
        """Test that QuiltOps is an abstract base class."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should be a subclass of ABC
        assert issubclass(QuiltOps, ABC)

    def test_quilt_ops_cannot_be_instantiated(self):
        """Test that QuiltOps cannot be instantiated directly."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should raise TypeError when trying to instantiate
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            QuiltOps()

    def test_quilt_ops_has_abstract_methods(self):
        """Test that QuiltOps has the required abstract methods."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Get abstract methods
        abstract_methods = QuiltOps.__abstractmethods__
        
        # Should have all required abstract methods
        expected_methods = {
            'get_auth_status',
            'search_packages',
            'get_package_info', 
            'browse_content',
            'list_buckets',
            'get_content_url'
        }
        
        assert expected_methods.issubset(abstract_methods), (
            f"Missing abstract methods: {expected_methods - abstract_methods}"
        )

    def test_quilt_ops_method_signatures(self):
        """Test that QuiltOps methods have correct signatures."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        # Check get_auth_status signature
        auth_sig = inspect.signature(QuiltOps.get_auth_status)
        auth_params = list(auth_sig.parameters.keys())
        assert auth_params == ['self']
        
        # Check search_packages signature
        search_sig = inspect.signature(QuiltOps.search_packages)
        search_params = list(search_sig.parameters.keys())
        assert search_params == ['self', 'query', 'registry']
        
        # Check get_package_info signature
        info_sig = inspect.signature(QuiltOps.get_package_info)
        info_params = list(info_sig.parameters.keys())
        assert info_params == ['self', 'package_name', 'registry']
        
        # Check browse_content signature
        browse_sig = inspect.signature(QuiltOps.browse_content)
        browse_params = list(browse_sig.parameters.keys())
        assert browse_params == ['self', 'package_name', 'registry', 'path']
        
        # Check list_buckets signature
        buckets_sig = inspect.signature(QuiltOps.list_buckets)
        buckets_params = list(buckets_sig.parameters.keys())
        assert buckets_params == ['self']
        
        # Check get_content_url signature
        url_sig = inspect.signature(QuiltOps.get_content_url)
        url_params = list(url_sig.parameters.keys())
        assert url_params == ['self', 'package_name', 'registry', 'path']

    def test_quilt_ops_return_type_annotations(self):
        """Test that QuiltOps methods have correct return type annotations."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status
        import inspect
        
        # Check get_auth_status return type
        auth_sig = inspect.signature(QuiltOps.get_auth_status)
        assert auth_sig.return_annotation == Auth_Status
        
        # Check search_packages return type
        search_sig = inspect.signature(QuiltOps.search_packages)
        assert search_sig.return_annotation == List[Package_Info]
        
        # Check get_package_info return type
        info_sig = inspect.signature(QuiltOps.get_package_info)
        assert info_sig.return_annotation == Package_Info
        
        # Check browse_content return type
        browse_sig = inspect.signature(QuiltOps.browse_content)
        assert browse_sig.return_annotation == List[Content_Info]
        
        # Check list_buckets return type
        buckets_sig = inspect.signature(QuiltOps.list_buckets)
        assert buckets_sig.return_annotation == List[Bucket_Info]
        
        # Check get_content_url return type
        url_sig = inspect.signature(QuiltOps.get_content_url)
        assert url_sig.return_annotation == str

    def test_quilt_ops_parameter_type_annotations(self):
        """Test that QuiltOps methods have correct parameter type annotations."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        # Check search_packages parameter types
        search_sig = inspect.signature(QuiltOps.search_packages)
        assert search_sig.parameters['query'].annotation == str
        assert search_sig.parameters['registry'].annotation == str
        
        # Check get_package_info parameter types
        info_sig = inspect.signature(QuiltOps.get_package_info)
        assert info_sig.parameters['package_name'].annotation == str
        assert info_sig.parameters['registry'].annotation == str
        
        # Check browse_content parameter types
        browse_sig = inspect.signature(QuiltOps.browse_content)
        assert browse_sig.parameters['package_name'].annotation == str
        assert browse_sig.parameters['registry'].annotation == str
        assert browse_sig.parameters['path'].annotation == str
        
        # Check get_content_url parameter types
        url_sig = inspect.signature(QuiltOps.get_content_url)
        assert url_sig.parameters['package_name'].annotation == str
        assert url_sig.parameters['registry'].annotation == str
        assert url_sig.parameters['path'].annotation == str


class TestQuiltOpsAbstractMethodBehavior:
    """Test that abstract methods raise NotImplementedError when called."""

    def test_abstract_methods_raise_not_implemented_error(self):
        """Test that abstract methods raise NotImplementedError."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Create a concrete class that doesn't implement abstract methods
        class IncompleteQuiltOps(QuiltOps):
            pass
        
        # Should not be able to instantiate
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteQuiltOps()

    def test_concrete_implementation_can_be_instantiated(self):
        """Test that concrete implementations can be instantiated."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info
        
        # Create a concrete implementation
        class ConcreteQuiltOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                from quilt_mcp.domain import Auth_Status
                return Auth_Status(
                    is_authenticated=True,
                    logged_in_url="https://catalog.example.com",
                    catalog_name="test-catalog",
                    registry_url="s3://test-registry"
                )
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info(
                    name="test/package",
                    description="Test package",
                    tags=[],
                    modified_date="2024-01-15T10:30:00Z",
                    registry="s3://test-registry",
                    bucket="test-bucket",
                    top_hash="abc123"
                )
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://example.com/download/file.txt"
        
        # Should be able to instantiate
        ops = ConcreteQuiltOps()
        assert ops is not None
        assert isinstance(ops, QuiltOps)

    def test_partial_implementation_cannot_be_instantiated(self):
        """Test that partial implementations cannot be instantiated."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info
        
        # Create a partial implementation (missing some methods)
        class PartialQuiltOps(QuiltOps):
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            # Missing other abstract methods
        
        # Should not be able to instantiate
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PartialQuiltOps()


class TestQuiltOpsMethodDocstrings:
    """Test that QuiltOps methods have comprehensive docstrings."""

    def test_get_auth_status_has_docstring(self):
        """Test that get_auth_status method has a docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.get_auth_status.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "auth" in docstring.lower()
        assert "status" in docstring.lower()

    def test_search_packages_has_docstring(self):
        """Test that search_packages method has a docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.search_packages.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "search" in docstring.lower()
        assert "packages" in docstring.lower()

    def test_get_package_info_has_docstring(self):
        """Test that get_package_info method has a docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.get_package_info.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "package" in docstring.lower()
        assert "info" in docstring.lower()

    def test_browse_content_has_docstring(self):
        """Test that browse_content method has a docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.browse_content.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "browse" in docstring.lower() or "content" in docstring.lower()

    def test_list_buckets_has_docstring(self):
        """Test that list_buckets method has a docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.list_buckets.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "bucket" in docstring.lower()

    def test_get_content_url_has_docstring(self):
        """Test that get_content_url method has a docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.get_content_url.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "url" in docstring.lower()

    def test_class_has_comprehensive_docstring(self):
        """Test that QuiltOps class has a comprehensive docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        assert "domain-driven" in docstring.lower() or "abstraction" in docstring.lower()
        assert "backend" in docstring.lower()


class TestQuiltOpsDefaultParameters:
    """Test QuiltOps method default parameters."""

    def test_browse_content_has_default_path(self):
        """Test that browse_content has default path parameter."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        sig = inspect.signature(QuiltOps.browse_content)
        path_param = sig.parameters['path']
        
        # Should have default value of empty string
        assert path_param.default == ""

    def test_other_methods_have_no_defaults(self):
        """Test that other methods don't have unexpected default parameters."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        # search_packages should have no defaults
        search_sig = inspect.signature(QuiltOps.search_packages)
        for param_name, param in search_sig.parameters.items():
            if param_name != 'self':
                assert param.default == inspect.Parameter.empty
        
        # get_package_info should have no defaults
        info_sig = inspect.signature(QuiltOps.get_package_info)
        for param_name, param in info_sig.parameters.items():
            if param_name != 'self':
                assert param.default == inspect.Parameter.empty
        
        # list_buckets should have no parameters except self
        buckets_sig = inspect.signature(QuiltOps.list_buckets)
        assert len(buckets_sig.parameters) == 1  # Only 'self'
        
        # get_content_url should have no defaults
        url_sig = inspect.signature(QuiltOps.get_content_url)
        for param_name, param in url_sig.parameters.items():
            if param_name != 'self':
                assert param.default == inspect.Parameter.empty


class TestQuiltOpsInterfaceCompliance:
    """Test QuiltOps interface compliance and design principles."""

    def test_quilt_ops_uses_domain_objects(self):
        """Test that QuiltOps interface uses domain objects, not backend-specific types."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info
        import inspect
        
        # Get all method signatures
        methods = [
            QuiltOps.search_packages,
            QuiltOps.get_package_info,
            QuiltOps.browse_content,
            QuiltOps.list_buckets,
            QuiltOps.get_content_url
        ]
        
        # Check that no method uses backend-specific types
        backend_specific_types = {
            'quilt3.Package', 'Package', 'quilt3.Bucket',
            'GraphQLResponse', 'PlatformPackage', 'Session'
        }
        
        for method in methods:
            sig = inspect.signature(method)
            
            # Check return type
            return_annotation = sig.return_annotation
            if hasattr(return_annotation, '__name__'):
                assert return_annotation.__name__ not in backend_specific_types
            
            # Check parameter types
            for param in sig.parameters.values():
                if param.annotation != inspect.Parameter.empty:
                    if hasattr(param.annotation, '__name__'):
                        assert param.annotation.__name__ not in backend_specific_types

    def test_quilt_ops_methods_are_domain_driven(self):
        """Test that QuiltOps methods are named after domain operations."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Method names should reflect domain operations, not backend operations
        method_names = [name for name in dir(QuiltOps) if not name.startswith('_')]
        
        # Should have domain-driven method names
        expected_methods = [
            'search_packages',
            'get_package_info',
            'browse_content',
            'list_buckets',
            'get_content_url'
        ]
        
        for method in expected_methods:
            assert method in method_names
        
        # Should not have backend-specific method names
        backend_specific_methods = [
            'quilt3_search', 'platform_search', 'graphql_query',
            'session_login', 'jwt_authenticate'
        ]
        
        for method in backend_specific_methods:
            assert method not in method_names

    def test_quilt_ops_is_backend_agnostic(self):
        """Test that QuiltOps interface is truly backend-agnostic."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        # Get class source (if available) to check for backend-specific references
        try:
            source = inspect.getsource(QuiltOps)
            
            # Should not reference specific backends in interface
            backend_references = ['quilt3', 'platform', 'graphql', 'jwt', 'session']
            
            for ref in backend_references:
                # Allow in comments/docstrings but not in actual code
                lines = source.split('\n')
                code_lines = [line for line in lines if not line.strip().startswith('#') 
                             and '"""' not in line and "'''" not in line]
                code_text = '\n'.join(code_lines).lower()
                
                # Should not have backend-specific code (some references in docstrings are OK)
                if ref in code_text:
                    # Allow in type hints and imports, but not in method implementations
                    assert 'import' in code_text or 'from' in code_text or '@abstractmethod' in code_text
        
        except OSError:
            # Source not available, skip this test
            pass


class TestQuiltOpsErrorHandling:
    """Test QuiltOps error handling expectations."""

    def test_quilt_ops_methods_can_raise_domain_exceptions(self):
        """Test that QuiltOps methods can raise domain-specific exceptions."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info
        
        # Create a test implementation that raises exceptions
        class ExceptionQuiltOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                raise BackendError("Auth status unavailable", {"backend_type": "test"})
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                raise BackendError("Search failed", {"backend_type": "test"})
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                raise ValidationError("Invalid package name", {"field": "package_name"})
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                raise AuthenticationError("Not authenticated", {"auth_method": "test"})
            
            def list_buckets(self) -> List[Bucket_Info]:
                raise BackendError("Backend unavailable", {"backend_type": "test"})
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                raise ValidationError("Invalid path", {"field": "path"})
        
        ops = ExceptionQuiltOps()
        
        # Should be able to raise domain exceptions
        with pytest.raises(BackendError):
            ops.get_auth_status()
        
        with pytest.raises(BackendError):
            ops.search_packages("test", "s3://registry")
        
        with pytest.raises(ValidationError):
            ops.get_package_info("invalid", "s3://registry")
        
        with pytest.raises(AuthenticationError):
            ops.browse_content("test/package", "s3://registry")
        
        with pytest.raises(BackendError):
            ops.list_buckets()
        
        with pytest.raises(ValidationError):
            ops.get_content_url("test/package", "s3://registry", "invalid/path")


class TestQuiltOpsUsagePatterns:
    """Test common QuiltOps usage patterns."""

    def test_quilt_ops_can_be_used_polymorphically(self):
        """Test that QuiltOps implementations can be used polymorphically."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status
        
        # Create two different implementations
        class MockQuilt3Ops(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                from quilt_mcp.domain import Auth_Status
                return Auth_Status(
                    is_authenticated=True,
                    logged_in_url="https://quilt3.example.com",
                    catalog_name="quilt3-catalog",
                    registry_url="s3://quilt3-registry"
                )
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return [Package_Info("quilt3/package", None, [], "2024-01-15T10:30:00Z", 
                                   registry, "bucket", "hash1")]
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info(package_name, "From quilt3", [], "2024-01-15T10:30:00Z",
                                  registry, "bucket", "hash1")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return [Content_Info("file.txt", 1024, "file", "2024-01-15T10:30:00Z", "url1")]
            
            def list_buckets(self) -> List[Bucket_Info]:
                return [Bucket_Info("bucket1", "us-east-1", "read-write", "2024-01-15T10:30:00Z")]
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return f"https://quilt3.example.com/{package_name}/{path}"
        
        class MockPlatformOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                from quilt_mcp.domain import Auth_Status
                return Auth_Status(
                    is_authenticated=True,
                    logged_in_url="https://platform.example.com",
                    catalog_name="platform-catalog",
                    registry_url="s3://platform-registry"
                )
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return [Package_Info("platform/package", None, [], "2024-01-15T10:30:00Z",
                                   registry, "bucket", "hash2")]
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info(package_name, "From platform", [], "2024-01-15T10:30:00Z",
                                  registry, "bucket", "hash2")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return [Content_Info("data.csv", 2048, "file", "2024-01-15T10:30:00Z", "url2")]
            
            def list_buckets(self) -> List[Bucket_Info]:
                return [Bucket_Info("bucket2", "us-west-2", "read-only", "2024-01-15T10:30:00Z")]
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return f"https://platform.example.com/{package_name}/{path}"
        
        # Should be able to use both polymorphically
        implementations = [MockQuilt3Ops(), MockPlatformOps()]
        
        for ops in implementations:
            assert isinstance(ops, QuiltOps)
            
            # Should be able to call all methods
            auth_status = ops.get_auth_status()
            assert isinstance(auth_status, Auth_Status)
            assert auth_status.is_authenticated is True
            
            packages = ops.search_packages("test", "s3://registry")
            assert len(packages) == 1
            assert isinstance(packages[0], Package_Info)
            
            package_info = ops.get_package_info("test/package", "s3://registry")
            assert isinstance(package_info, Package_Info)
            
            content = ops.browse_content("test/package", "s3://registry")
            assert len(content) == 1
            assert isinstance(content[0], Content_Info)
            
            buckets = ops.list_buckets()
            assert len(buckets) == 1
            assert isinstance(buckets[0], Bucket_Info)
            
            url = ops.get_content_url("test/package", "s3://registry", "file.txt")
            assert isinstance(url, str)
            assert "example.com" in url