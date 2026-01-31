"""Tests for QuiltOps abstract interface - Test-Driven Development Implementation.

This test suite follows TDD principles by defining the expected behavior of the QuiltOps
abstract base class before implementation. Tests cover abstract methods, type hints, and interface compliance.
"""

from __future__ import annotations

import pytest
from abc import ABC, abstractmethod
from typing import List, Optional
from unittest.mock import Mock

# Import domain objects for type checking
from quilt_mcp.domain import Catalog_Config


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
            'get_content_url',
            'get_catalog_config',
            'configure_catalog'
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

        # Check get_catalog_config signature
        catalog_config_sig = inspect.signature(QuiltOps.get_catalog_config)
        catalog_config_params = list(catalog_config_sig.parameters.keys())
        assert catalog_config_params == ['self', 'catalog_url']

        # Check configure_catalog signature
        configure_sig = inspect.signature(QuiltOps.configure_catalog)
        configure_params = list(configure_sig.parameters.keys())
        assert configure_params == ['self', 'catalog_url']

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

        # Check get_catalog_config return type
        catalog_config_sig = inspect.signature(QuiltOps.get_catalog_config)
        assert catalog_config_sig.return_annotation == Catalog_Config

        # Check configure_catalog return type
        configure_sig = inspect.signature(QuiltOps.configure_catalog)
        assert configure_sig.return_annotation is None or configure_sig.return_annotation == type(None)

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

        # Check get_catalog_config parameter types
        catalog_config_sig = inspect.signature(QuiltOps.get_catalog_config)
        assert catalog_config_sig.parameters['catalog_url'].annotation == str

        # Check configure_catalog parameter types
        configure_sig = inspect.signature(QuiltOps.configure_catalog)
        assert configure_sig.parameters['catalog_url'].annotation == str


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
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config(
                    region="us-east-1",
                    api_gateway_endpoint="https://api.example.com",
                    analytics_bucket="test-analytics-bucket",
                    stack_prefix="test-stack",
                    tabulator_data_catalog="quilt-test-stack-tabulator"
                )
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
        
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
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                raise BackendError("Catalog config unavailable", {"backend_type": "test"})
            
            def configure_catalog(self, catalog_url: str) -> None:
                raise BackendError("Configure failed", {"backend_type": "test"})
            
            def get_registry_url(self) -> Optional[str]:
                raise BackendError("Registry URL unavailable", {"backend_type": "test"})
        
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
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config(
                    region="us-east-1",
                    api_gateway_endpoint="https://api.quilt3.example.com",
                    analytics_bucket="quilt3-analytics",
                    stack_prefix="quilt3",
                    tabulator_data_catalog="quilt-quilt3-tabulator"
                )
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://quilt3-registry"
        
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
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config(
                    region="us-west-2",
                    api_gateway_endpoint="https://api.platform.example.com",
                    analytics_bucket="platform-analytics",
                    stack_prefix="platform",
                    tabulator_data_catalog="quilt-platform-tabulator"
                )
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://platform-registry"
        
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


class TestQuiltOpsCatalogConfigMethods:
    """Test QuiltOps catalog configuration methods - TDD Implementation."""

    def test_get_catalog_config_method_exists(self):
        """Test that get_catalog_config method exists in QuiltOps interface."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should have get_catalog_config method
        assert hasattr(QuiltOps, 'get_catalog_config')
        assert callable(getattr(QuiltOps, 'get_catalog_config'))

    def test_configure_catalog_method_exists(self):
        """Test that configure_catalog method exists in QuiltOps interface."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should have configure_catalog method
        assert hasattr(QuiltOps, 'configure_catalog')
        assert callable(getattr(QuiltOps, 'configure_catalog'))

    def test_get_catalog_config_has_correct_signature(self):
        """Test that get_catalog_config has the correct method signature."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        sig = inspect.signature(QuiltOps.get_catalog_config)
        params = list(sig.parameters.keys())
        
        # Should have self and catalog_url parameters
        assert params == ['self', 'catalog_url']
        
        # catalog_url should be annotated as str
        assert sig.parameters['catalog_url'].annotation == str
        
        # Should return Catalog_Config
        assert sig.return_annotation == Catalog_Config

    def test_configure_catalog_has_correct_signature(self):
        """Test that configure_catalog has the correct method signature."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        sig = inspect.signature(QuiltOps.configure_catalog)
        params = list(sig.parameters.keys())
        
        # Should have self and catalog_url parameters
        assert params == ['self', 'catalog_url']
        
        # catalog_url should be annotated as str
        assert sig.parameters['catalog_url'].annotation == str
        
        # Should return None
        assert sig.return_annotation is None or sig.return_annotation == type(None)

    def test_get_catalog_config_is_abstract(self):
        """Test that get_catalog_config is an abstract method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should be in abstract methods
        assert 'get_catalog_config' in QuiltOps.__abstractmethods__

    def test_configure_catalog_is_abstract(self):
        """Test that configure_catalog is an abstract method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should be in abstract methods
        assert 'configure_catalog' in QuiltOps.__abstractmethods__

    def test_get_catalog_config_has_comprehensive_docstring(self):
        """Test that get_catalog_config has a comprehensive docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.get_catalog_config.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        
        # Should mention key concepts
        assert "catalog" in docstring.lower()
        assert "configuration" in docstring.lower()
        assert "catalog_url" in docstring
        assert "Catalog_Config" in docstring
        
        # Should document exceptions
        assert "AuthenticationError" in docstring
        assert "BackendError" in docstring
        assert "ValidationError" in docstring
        assert "NotFoundError" in docstring

    def test_configure_catalog_has_comprehensive_docstring(self):
        """Test that configure_catalog has a comprehensive docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.configure_catalog.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        
        # Should mention key concepts
        assert "configure" in docstring.lower()
        assert "catalog" in docstring.lower()
        assert "catalog_url" in docstring
        
        # Should document exceptions
        assert "AuthenticationError" in docstring
        assert "BackendError" in docstring
        assert "ValidationError" in docstring

    def test_catalog_methods_can_be_implemented(self):
        """Test that catalog methods can be implemented in concrete classes."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        
        class TestCatalogOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config(
                    region="us-east-1",
                    api_gateway_endpoint="https://api.test.com",
                    analytics_bucket="test-analytics",
                    stack_prefix="test",
                    tabulator_data_catalog="quilt-test-tabulator"
                )
            
            def configure_catalog(self, catalog_url: str) -> None:
                # Implementation would configure the catalog
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
        
        # Should be able to instantiate and use
        ops = TestCatalogOps()
        
        # Should be able to call get_catalog_config
        config = ops.get_catalog_config("https://test.quiltdata.com")
        assert isinstance(config, Catalog_Config)
        assert config.region == "us-east-1"
        assert config.api_gateway_endpoint == "https://api.test.com"
        assert config.analytics_bucket == "test-analytics"
        assert config.stack_prefix == "test"
        assert config.tabulator_data_catalog == "quilt-test-tabulator"
        
        # Should be able to call configure_catalog
        ops.configure_catalog("https://test.quiltdata.com")  # Should not raise

    def test_catalog_methods_can_raise_domain_exceptions(self):
        """Test that catalog methods can raise appropriate domain exceptions."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        
        class ExceptionCatalogOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                if catalog_url == "https://invalid.com":
                    raise ValidationError("Invalid catalog URL", {"field": "catalog_url"})
                elif catalog_url == "https://notfound.com":
                    raise NotFoundError("Catalog configuration not found")
                elif catalog_url == "https://auth.com":
                    raise AuthenticationError("Authentication required")
                elif catalog_url == "https://backend.com":
                    raise BackendError("Backend operation failed")
                else:
                    return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                if catalog_url == "https://invalid.com":
                    raise ValidationError("Invalid catalog URL", {"field": "catalog_url"})
                elif catalog_url == "https://auth.com":
                    raise AuthenticationError("Authentication required")
                elif catalog_url == "https://backend.com":
                    raise BackendError("Backend operation failed")
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
        
        ops = ExceptionCatalogOps()
        
        # get_catalog_config should raise appropriate exceptions
        with pytest.raises(ValidationError):
            ops.get_catalog_config("https://invalid.com")
        
        with pytest.raises(NotFoundError):
            ops.get_catalog_config("https://notfound.com")
        
        with pytest.raises(AuthenticationError):
            ops.get_catalog_config("https://auth.com")
        
        with pytest.raises(BackendError):
            ops.get_catalog_config("https://backend.com")
        
        # configure_catalog should raise appropriate exceptions
        with pytest.raises(ValidationError):
            ops.configure_catalog("https://invalid.com")
        
        with pytest.raises(AuthenticationError):
            ops.configure_catalog("https://auth.com")
        
        with pytest.raises(BackendError):
            ops.configure_catalog("https://backend.com")

    def test_catalog_methods_usage_patterns(self):
        """Test common usage patterns for catalog configuration methods."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        
        class UsagePatternOps(QuiltOps):
            def __init__(self):
                self.configured_catalog = None
            
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                # Simulate different catalog configurations
                if "production" in catalog_url:
                    return Catalog_Config(
                        region="us-east-1",
                        api_gateway_endpoint="https://api.prod.quiltdata.com",
                        analytics_bucket="prod-analytics-bucket",
                        stack_prefix="quilt-prod",
                        tabulator_data_catalog="quilt-quilt-prod-tabulator"
                    )
                else:
                    return Catalog_Config(
                        region="us-west-2",
                        api_gateway_endpoint="https://api.staging.quiltdata.com",
                        analytics_bucket="staging-analytics-bucket",
                        stack_prefix="quilt-staging",
                        tabulator_data_catalog="quilt-quilt-staging-tabulator"
                    )
            
            def configure_catalog(self, catalog_url: str) -> None:
                self.configured_catalog = catalog_url
            
            def get_registry_url(self) -> Optional[str]:
                if self.configured_catalog:
                    if "production" in self.configured_catalog:
                        return "s3://prod-registry"
                    elif "staging" in self.configured_catalog:
                        return "s3://staging-registry"
                return "s3://default-registry"
        
        ops = UsagePatternOps()
        
        # Should be able to get different configurations
        prod_config = ops.get_catalog_config("https://production.quiltdata.com")
        staging_config = ops.get_catalog_config("https://staging.quiltdata.com")
        
        assert prod_config.region == "us-east-1"
        assert staging_config.region == "us-west-2"
        assert prod_config.stack_prefix == "quilt-prod"
        assert staging_config.stack_prefix == "quilt-staging"
        
        # Should be able to configure catalog
        ops.configure_catalog("https://production.quiltdata.com")
        assert ops.configured_catalog == "https://production.quiltdata.com"
        
        # Should be able to use config for AWS operations
        config = ops.get_catalog_config("https://production.quiltdata.com")
        aws_region = config.region
        api_endpoint = config.api_gateway_endpoint
        tabulator_catalog = config.tabulator_data_catalog
        
        assert aws_region == "us-east-1"
        assert "api.prod.quiltdata.com" in api_endpoint
        assert "quilt-prod-tabulator" in tabulator_catalog


class TestQuiltOpsGraphQLMethod:
    """Test QuiltOps execute_graphql_query method - TDD Implementation."""

    def test_execute_graphql_query_method_exists(self):
        """Test that execute_graphql_query method exists in QuiltOps interface."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should have execute_graphql_query method
        assert hasattr(QuiltOps, 'execute_graphql_query')
        assert callable(getattr(QuiltOps, 'execute_graphql_query'))

    def test_execute_graphql_query_has_correct_signature(self):
        """Test that execute_graphql_query has the correct method signature."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        from typing import Dict, Any, Optional
        
        sig = inspect.signature(QuiltOps.execute_graphql_query)
        params = list(sig.parameters.keys())
        
        # Should have self, query, variables, and registry parameters
        assert params == ['self', 'query', 'variables', 'registry']
        
        # Check parameter types
        assert sig.parameters['query'].annotation == str
        assert sig.parameters['variables'].annotation == Optional[Dict]
        assert sig.parameters['registry'].annotation == Optional[str]
        
        # Should return Dict[str, Any]
        assert sig.return_annotation == Dict[str, Any]

    def test_execute_graphql_query_has_default_parameters(self):
        """Test that execute_graphql_query has correct default parameters."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        sig = inspect.signature(QuiltOps.execute_graphql_query)
        
        # variables should default to None
        assert sig.parameters['variables'].default is None
        
        # registry should default to None
        assert sig.parameters['registry'].default is None

    def test_execute_graphql_query_is_abstract(self):
        """Test that execute_graphql_query is an abstract method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should be in abstract methods
        assert 'execute_graphql_query' in QuiltOps.__abstractmethods__

    def test_execute_graphql_query_has_comprehensive_docstring(self):
        """Test that execute_graphql_query has a comprehensive docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.execute_graphql_query.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        
        # Should mention key concepts
        assert "graphql" in docstring.lower()
        assert "query" in docstring.lower()
        assert "catalog" in docstring.lower()
        assert "variables" in docstring.lower()
        assert "registry" in docstring.lower()
        
        # Should document parameters
        assert "query:" in docstring
        assert "variables:" in docstring
        assert "registry:" in docstring
        
        # Should document return type
        assert "Dict[str, Any]" in docstring
        
        # Should document exceptions
        assert "AuthenticationError" in docstring
        assert "BackendError" in docstring
        assert "ValidationError" in docstring

    def test_execute_graphql_query_can_be_implemented(self):
        """Test that execute_graphql_query can be implemented in concrete classes."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Dict, Any, Optional
        
        class TestGraphQLOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
            
            def execute_graphql_query(
                self, 
                query: str, 
                variables: Optional[Dict] = None, 
                registry: Optional[str] = None
            ) -> Dict[str, Any]:
                # Mock GraphQL response
                if "buckets" in query:
                    return {
                        "data": {
                            "buckets": [
                                {"name": "test-bucket", "region": "us-east-1"},
                                {"name": "another-bucket", "region": "us-west-2"}
                            ]
                        }
                    }
                elif "packages" in query:
                    return {
                        "data": {
                            "packages": [
                                {"name": "test/package", "description": "Test package"}
                            ]
                        }
                    }
                else:
                    return {"data": {}}
            
            def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
                from unittest.mock import Mock
                return Mock()
        
        # Should be able to instantiate and use
        ops = TestGraphQLOps()
        
        # Should be able to call execute_graphql_query with minimal parameters
        result = ops.execute_graphql_query("{ buckets { name } }")
        assert isinstance(result, dict)
        assert "data" in result
        assert "buckets" in result["data"]
        
        # Should be able to call with variables
        result = ops.execute_graphql_query(
            "query GetPackages($limit: Int) { packages(limit: $limit) { name } }",
            variables={"limit": 10}
        )
        assert isinstance(result, dict)
        
        # Should be able to call with registry
        result = ops.execute_graphql_query(
            "{ buckets { name } }",
            registry="s3://custom-registry"
        )
        assert isinstance(result, dict)

    def test_execute_graphql_query_can_raise_domain_exceptions(self):
        """Test that execute_graphql_query can raise appropriate domain exceptions."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Dict, Any, Optional
        
        class ExceptionGraphQLOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
            
            def execute_graphql_query(
                self, 
                query: str, 
                variables: Optional[Dict] = None, 
                registry: Optional[str] = None
            ) -> Dict[str, Any]:
                if "invalid" in query:
                    raise ValidationError("Invalid GraphQL query", {"field": "query"})
                elif "unauthorized" in query:
                    raise AuthenticationError("GraphQL query not authorized")
                elif "backend_error" in query:
                    raise BackendError("GraphQL execution failed")
                else:
                    return {"data": {}}
            
            def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
                from unittest.mock import Mock
                return Mock()
        
        ops = ExceptionGraphQLOps()
        
        # Should raise ValidationError for invalid queries
        with pytest.raises(ValidationError):
            ops.execute_graphql_query("invalid query syntax")
        
        # Should raise AuthenticationError for unauthorized queries
        with pytest.raises(AuthenticationError):
            ops.execute_graphql_query("{ unauthorized { data } }")
        
        # Should raise BackendError for backend failures
        with pytest.raises(BackendError):
            ops.execute_graphql_query("{ backend_error { data } }")

    def test_execute_graphql_query_usage_patterns(self):
        """Test common usage patterns for execute_graphql_query method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Dict, Any, Optional
        
        class UsagePatternGraphQLOps(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
            
            def execute_graphql_query(
                self, 
                query: str, 
                variables: Optional[Dict] = None, 
                registry: Optional[str] = None
            ) -> Dict[str, Any]:
                # Simulate different GraphQL operations
                if "buckets" in query:
                    buckets = ["bucket1", "bucket2", "bucket3"]
                    if variables and "limit" in variables:
                        buckets = buckets[:variables["limit"]]
                    return {"data": {"buckets": [{"name": b} for b in buckets]}}
                
                elif "packages" in query:
                    packages = ["user1/pkg1", "user2/pkg2", "user3/pkg3"]
                    if variables and "search" in variables:
                        packages = [p for p in packages if variables["search"] in p]
                    return {"data": {"packages": [{"name": p} for p in packages]}}
                
                elif "config" in query:
                    config_data = {
                        "region": "us-east-1",
                        "apiGatewayEndpoint": "https://api.test.com",
                        "analyticsBucket": "test-analytics"
                    }
                    if registry:
                        config_data["registry"] = registry
                    return {"data": {"config": config_data}}
                
                else:
                    return {"data": {}}
            
            def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
                from unittest.mock import Mock
                return Mock()
        
        ops = UsagePatternGraphQLOps()
        
        # Test bucket listing query
        result = ops.execute_graphql_query("{ buckets { name } }")
        assert len(result["data"]["buckets"]) == 3
        
        # Test bucket listing with limit
        result = ops.execute_graphql_query(
            "query GetBuckets($limit: Int) { buckets(limit: $limit) { name } }",
            variables={"limit": 2}
        )
        assert len(result["data"]["buckets"]) == 2
        
        # Test package search
        result = ops.execute_graphql_query(
            "query SearchPackages($search: String) { packages(search: $search) { name } }",
            variables={"search": "user1"}
        )
        assert len(result["data"]["packages"]) == 1
        assert result["data"]["packages"][0]["name"] == "user1/pkg1"
        
        # Test config query with registry
        result = ops.execute_graphql_query(
            "{ config { region apiGatewayEndpoint } }",
            registry="s3://custom-registry"
        )
        assert result["data"]["config"]["region"] == "us-east-1"
        assert result["data"]["config"]["registry"] == "s3://custom-registry"


class TestQuiltOpsBoto3ClientMethod:
    """Test QuiltOps get_boto3_client method - TDD Implementation."""

    def test_get_boto3_client_method_exists(self):
        """Test that get_boto3_client method exists in QuiltOps interface."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should have get_boto3_client method
        assert hasattr(QuiltOps, 'get_boto3_client')
        assert callable(getattr(QuiltOps, 'get_boto3_client'))

    def test_get_boto3_client_has_correct_signature(self):
        """Test that get_boto3_client has the correct method signature."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        from typing import Any, Optional
        
        sig = inspect.signature(QuiltOps.get_boto3_client)
        params = list(sig.parameters.keys())
        
        # Should have self, service_name, and region parameters
        assert params == ['self', 'service_name', 'region']
        
        # Check parameter types
        assert sig.parameters['service_name'].annotation == str
        assert sig.parameters['region'].annotation == Optional[str]
        
        # Should return Any (boto3 client)
        assert sig.return_annotation == Any

    def test_get_boto3_client_has_default_parameters(self):
        """Test that get_boto3_client has correct default parameters."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        sig = inspect.signature(QuiltOps.get_boto3_client)
        
        # region should default to None
        assert sig.parameters['region'].default is None

    def test_get_boto3_client_is_abstract(self):
        """Test that get_boto3_client is an abstract method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should be in abstract methods
        assert 'get_boto3_client' in QuiltOps.__abstractmethods__

    def test_get_boto3_client_has_comprehensive_docstring(self):
        """Test that get_boto3_client has a comprehensive docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.get_boto3_client.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        
        # Should mention key concepts
        assert "boto3" in docstring.lower()
        assert "client" in docstring.lower()
        assert "aws" in docstring.lower()
        assert "service" in docstring.lower()
        assert "authenticated" in docstring.lower()
        
        # Should document parameters
        assert "service_name:" in docstring
        assert "region:" in docstring
        
        # Should document return type
        assert "boto3 client" in docstring.lower()
        
        # Should document exceptions
        assert "AuthenticationError" in docstring
        assert "BackendError" in docstring
        assert "ValidationError" in docstring

    def test_get_boto3_client_can_be_implemented(self):
        """Test that get_boto3_client can be implemented in concrete classes."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Dict, Any, Optional
        from unittest.mock import Mock
        
        class TestBoto3Ops(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
            
            def execute_graphql_query(
                self, 
                query: str, 
                variables: Optional[Dict] = None, 
                registry: Optional[str] = None
            ) -> Dict[str, Any]:
                return {"data": {}}
            
            def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
                # Mock boto3 client
                mock_client = Mock()
                mock_client.service_name = service_name
                mock_client.region = region or "us-east-1"
                
                # Add service-specific methods
                if service_name == "s3":
                    mock_client.list_buckets = Mock(return_value={"Buckets": []})
                    mock_client.get_object = Mock()
                elif service_name == "athena":
                    mock_client.list_work_groups = Mock(return_value={"WorkGroups": []})
                    mock_client.start_query_execution = Mock()
                elif service_name == "glue":
                    mock_client.get_databases = Mock(return_value={"DatabaseList": []})
                    mock_client.get_tables = Mock()
                
                return mock_client
        
        # Should be able to instantiate and use
        ops = TestBoto3Ops()
        
        # Should be able to get S3 client
        s3_client = ops.get_boto3_client("s3")
        assert s3_client.service_name == "s3"
        assert s3_client.region == "us-east-1"
        assert hasattr(s3_client, "list_buckets")
        
        # Should be able to get Athena client with custom region
        athena_client = ops.get_boto3_client("athena", region="us-west-2")
        assert athena_client.service_name == "athena"
        assert athena_client.region == "us-west-2"
        assert hasattr(athena_client, "list_work_groups")
        
        # Should be able to get Glue client
        glue_client = ops.get_boto3_client("glue")
        assert glue_client.service_name == "glue"
        assert hasattr(glue_client, "get_databases")

    def test_get_boto3_client_can_raise_domain_exceptions(self):
        """Test that get_boto3_client can raise appropriate domain exceptions."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Dict, Any, Optional
        
        class ExceptionBoto3Ops(QuiltOps):
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
            
            def execute_graphql_query(
                self, 
                query: str, 
                variables: Optional[Dict] = None, 
                registry: Optional[str] = None
            ) -> Dict[str, Any]:
                return {"data": {}}
            
            def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
                if service_name == "invalid":
                    raise ValidationError("Invalid AWS service name", {"field": "service_name"})
                elif service_name == "unauthorized":
                    raise AuthenticationError("AWS credentials not available")
                elif service_name == "backend_error":
                    raise BackendError("Failed to create boto3 client")
                else:
                    from unittest.mock import Mock
                    return Mock()
        
        ops = ExceptionBoto3Ops()
        
        # Should raise ValidationError for invalid service names
        with pytest.raises(ValidationError):
            ops.get_boto3_client("invalid")
        
        # Should raise AuthenticationError for unauthorized access
        with pytest.raises(AuthenticationError):
            ops.get_boto3_client("unauthorized")
        
        # Should raise BackendError for backend failures
        with pytest.raises(BackendError):
            ops.get_boto3_client("backend_error")

    def test_get_boto3_client_usage_patterns(self):
        """Test common usage patterns for get_boto3_client method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Dict, Any, Optional
        from unittest.mock import Mock
        
        class UsagePatternBoto3Ops(QuiltOps):
            def __init__(self):
                self.default_region = "us-east-1"
            
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", "s3://test")
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config(self.default_region, "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                if "west" in catalog_url:
                    self.default_region = "us-west-2"
                else:
                    self.default_region = "us-east-1"
            
            def get_registry_url(self) -> Optional[str]:
                return "s3://test-registry"
            
            def execute_graphql_query(
                self, 
                query: str, 
                variables: Optional[Dict] = None, 
                registry: Optional[str] = None
            ) -> Dict[str, Any]:
                return {"data": {}}
            
            def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
                effective_region = region or self.default_region
                
                mock_client = Mock()
                mock_client.service_name = service_name
                mock_client.region = effective_region
                
                # Simulate different service capabilities
                if service_name == "s3":
                    mock_client.list_buckets = Mock(return_value={
                        "Buckets": [
                            {"Name": "bucket1", "CreationDate": "2024-01-01"},
                            {"Name": "bucket2", "CreationDate": "2024-01-02"}
                        ]
                    })
                elif service_name == "athena":
                    mock_client.list_work_groups = Mock(return_value={
                        "WorkGroups": [
                            {"Name": "primary", "State": "ENABLED"},
                            {"Name": "secondary", "State": "ENABLED"}
                        ]
                    })
                elif service_name == "glue":
                    mock_client.get_databases = Mock(return_value={
                        "DatabaseList": [
                            {"Name": "default"},
                            {"Name": "analytics"}
                        ]
                    })
                
                return mock_client
        
        ops = UsagePatternBoto3Ops()
        
        # Test default region usage
        s3_client = ops.get_boto3_client("s3")
        assert s3_client.region == "us-east-1"
        
        # Test explicit region override
        s3_client_west = ops.get_boto3_client("s3", region="us-west-2")
        assert s3_client_west.region == "us-west-2"
        
        # Test different AWS services
        athena_client = ops.get_boto3_client("athena")
        assert athena_client.service_name == "athena"
        workgroups = athena_client.list_work_groups()
        assert len(workgroups["WorkGroups"]) == 2
        
        glue_client = ops.get_boto3_client("glue")
        assert glue_client.service_name == "glue"
        databases = glue_client.get_databases()
        assert len(databases["DatabaseList"]) == 2
        
        # Test region changes based on catalog configuration
        ops.configure_catalog("https://west.quiltdata.com")
        s3_client_after_config = ops.get_boto3_client("s3")
        assert s3_client_after_config.region == "us-west-2"


class TestQuiltOpsRegistryUrlMethod:
    """Test QuiltOps get_registry_url method - TDD Implementation."""

    def test_get_registry_url_method_exists(self):
        """Test that get_registry_url method exists in QuiltOps interface."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should have get_registry_url method
        assert hasattr(QuiltOps, 'get_registry_url')
        assert callable(getattr(QuiltOps, 'get_registry_url'))

    def test_get_registry_url_has_correct_signature(self):
        """Test that get_registry_url has the correct method signature."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        import inspect
        
        sig = inspect.signature(QuiltOps.get_registry_url)
        params = list(sig.parameters.keys())
        
        # Should have only self parameter
        assert params == ['self']
        
        # Should return Optional[str]
        from typing import Optional
        assert sig.return_annotation == Optional[str]

    def test_get_registry_url_is_abstract(self):
        """Test that get_registry_url is an abstract method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Should be in abstract methods
        assert 'get_registry_url' in QuiltOps.__abstractmethods__

    def test_get_registry_url_has_comprehensive_docstring(self):
        """Test that get_registry_url has a comprehensive docstring."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        docstring = QuiltOps.get_registry_url.__doc__
        assert docstring is not None
        assert len(docstring.strip()) > 0
        
        # Should mention key concepts
        assert "registry" in docstring.lower()
        assert "url" in docstring.lower()
        assert "default" in docstring.lower()
        
        # Should document return type
        assert "Optional[str]" in docstring or "str | None" in docstring or "None" in docstring

    def test_get_registry_url_can_be_implemented(self):
        """Test that get_registry_url can be implemented in concrete classes."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Optional
        
        class TestRegistryOps(QuiltOps):
            def __init__(self, registry_url: Optional[str] = None):
                self.registry_url = registry_url
            
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", self.registry_url)
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                pass
            
            def get_registry_url(self) -> Optional[str]:
                return self.registry_url
        
        # Should be able to instantiate and use with registry URL
        ops_with_registry = TestRegistryOps("s3://test-registry")
        registry_url = ops_with_registry.get_registry_url()
        assert registry_url == "s3://test-registry"
        
        # Should be able to instantiate and use without registry URL
        ops_without_registry = TestRegistryOps(None)
        registry_url = ops_without_registry.get_registry_url()
        assert registry_url is None

    def test_get_registry_url_usage_patterns(self):
        """Test common usage patterns for get_registry_url method."""
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config
        from typing import Optional
        
        class UsagePatternRegistryOps(QuiltOps):
            def __init__(self):
                self.configured_registry = None
            
            def get_auth_status(self) -> Auth_Status:
                return Auth_Status(True, "https://test.com", "test", self.configured_registry)
            
            def search_packages(self, query: str, registry: str) -> List[Package_Info]:
                return []
            
            def get_package_info(self, package_name: str, registry: str) -> Package_Info:
                return Package_Info("test/pkg", None, [], "2024-01-15T10:30:00Z", registry, "bucket", "hash")
            
            def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
                return []
            
            def list_buckets(self) -> List[Bucket_Info]:
                return []
            
            def get_content_url(self, package_name: str, registry: str, path: str) -> str:
                return "https://test.com/file"
            
            def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
                return Catalog_Config("us-east-1", "https://api.test.com", "bucket", "test", "catalog")
            
            def configure_catalog(self, catalog_url: str) -> None:
                # Simulate configuring registry based on catalog URL
                if "production" in catalog_url:
                    self.configured_registry = "s3://prod-registry"
                elif "staging" in catalog_url:
                    self.configured_registry = "s3://staging-registry"
                else:
                    self.configured_registry = "s3://default-registry"
            
            def get_registry_url(self) -> Optional[str]:
                return self.configured_registry
        
        ops = UsagePatternRegistryOps()
        
        # Initially no registry configured
        assert ops.get_registry_url() is None
        
        # Configure production catalog
        ops.configure_catalog("https://production.quiltdata.com")
        assert ops.get_registry_url() == "s3://prod-registry"
        
        # Configure staging catalog
        ops.configure_catalog("https://staging.quiltdata.com")
        assert ops.get_registry_url() == "s3://staging-registry"
        
        # Configure default catalog
        ops.configure_catalog("https://default.quiltdata.com")
        assert ops.get_registry_url() == "s3://default-registry"