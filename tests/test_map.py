import unittest
import tempfile
import os
from pathlib import Path
from core.map import AtlasMap
from rich.tree import Tree


class TestAtlasMap(unittest.TestCase):
    """Test suite for AtlasMap class"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.atlas_map = None

    def tearDown(self):
        """Clean up after each test method"""
        # Remove temporary directory and its contents
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test AtlasMap initialization with a valid directory"""
        atlas_map = AtlasMap(self.test_dir)
        self.assertEqual(atlas_map.root_dir, self.test_dir)

    def test_generate_returns_tree(self):
        """Test that generate() returns a Tree object"""
        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        self.assertIsInstance(tree, Tree)

    def test_generate_empty_directory(self):
        """Test generate() on an empty directory"""
        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        self.assertIsInstance(tree, Tree)
        # Tree should exist but have no children
        self.assertEqual(len(tree.children), 0)

    def test_generate_with_files(self):
        """Test generate() with simple files in directory"""
        # Create test files
        test_file1 = os.path.join(self.test_dir, "test.py")
        test_file2 = os.path.join(self.test_dir, "readme.txt")
        Path(test_file1).touch()
        Path(test_file2).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have 2 children (2 files)
        self.assertEqual(len(tree.children), 2)

    def test_generate_with_subdirectories(self):
        """Test generate() with subdirectories"""
        # Create subdirectory structure
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)
        Path(os.path.join(subdir, "file.py")).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have 1 child (the subdirectory)
        self.assertEqual(len(tree.children), 1)

    def test_ignore_folders_pycache(self):
        """Test that __pycache__ folders are ignored"""
        # Create __pycache__ directory
        pycache_dir = os.path.join(self.test_dir, "__pycache__")
        os.makedirs(pycache_dir)
        Path(os.path.join(pycache_dir, "test.pyc")).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have 0 children (__pycache__ ignored)
        self.assertEqual(len(tree.children), 0)

    def test_ignore_folders_node_modules(self):
        """Test that node_modules folder is ignored"""
        # Create node_modules directory
        node_modules = os.path.join(self.test_dir, "node_modules")
        os.makedirs(node_modules)
        Path(os.path.join(node_modules, "package.json")).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have 0 children (node_modules ignored)
        self.assertEqual(len(tree.children), 0)

    def test_ignore_hidden_files(self):
        """Test that hidden files (starting with .) are ignored"""
        # Create hidden file
        hidden_file = os.path.join(self.test_dir, ".hidden")
        Path(hidden_file).touch()
        
        # Create normal file
        normal_file = os.path.join(self.test_dir, "visible.txt")
        Path(normal_file).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have 1 child (only visible.txt)
        self.assertEqual(len(tree.children), 1)

    def test_ignore_folders_constant(self):
        """Test that IGNORE_FOLDERS constant contains expected values"""
        expected_folders = {"__pycache__", "node_modules", "venv", ".git"}
        self.assertTrue(expected_folders.issubset(AtlasMap.IGNORE_FOLDERS))

    def test_max_files_limit(self):
        """Test that files are limited to MAX_FILES_PER_DIR"""
        # Create more files than the limit
        num_files = 15
        for i in range(num_files):
            test_file = os.path.join(self.test_dir, f"file{i}.txt")
            Path(test_file).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have MAX_FILES_PER_DIR files + 1 "more files" message
        # Total children = 10 files + 1 message = 11
        self.assertEqual(len(tree.children), atlas_map.MAX_FILES_PER_DIR + 1)

    def test_files_under_limit(self):
        """Test that all files are shown when under the limit"""
        # Create fewer files than the limit
        num_files = 5
        for i in range(num_files):
            test_file = os.path.join(self.test_dir, f"file{i}.txt")
            Path(test_file).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have exactly num_files children (no "more files" message)
        self.assertEqual(len(tree.children), num_files)

    def test_directories_not_limited(self):
        """Test that subdirectories are always shown, not limited"""
        # Create many subdirectories (more than MAX_FILES_PER_DIR)
        num_dirs = 15
        for i in range(num_dirs):
            subdir = os.path.join(self.test_dir, f"subdir{i}")
            os.makedirs(subdir)

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # All directories should be shown (no limit on directories)
        self.assertEqual(len(tree.children), num_dirs)

    def test_mixed_files_and_directories(self):
        """Test that directories are shown and files are limited separately"""
        # Create 5 directories and 15 files
        num_dirs = 5
        num_files = 15
        
        for i in range(num_dirs):
            subdir = os.path.join(self.test_dir, f"subdir{i}")
            os.makedirs(subdir)
        
        for i in range(num_files):
            test_file = os.path.join(self.test_dir, f"file{i}.txt")
            Path(test_file).touch()

        atlas_map = AtlasMap(self.test_dir)
        tree = atlas_map.generate()
        
        # Should have 5 dirs + 10 files (limit) + 1 "more files" message = 16
        expected_children = num_dirs + atlas_map.MAX_FILES_PER_DIR + 1
        self.assertEqual(len(tree.children), expected_children)



class TestAtlasMapPermissions(unittest.TestCase):
    """Test suite for permission-related functionality"""

    def test_permission_error_handling(self):
        """Test handling of directories with restricted permissions"""
        # This test is platform-dependent and may not work on all systems
        # Skip implementation for now - placeholder for future
        pass


if __name__ == "__main__":
    unittest.main()
