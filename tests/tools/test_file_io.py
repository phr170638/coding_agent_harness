"""文件 I/O 工具测试。"""

from myagent.tools.file_io import read_file, write_file


class TestReadFile:
    async def test_read_existing_file(self, temp_dir):
        filepath = temp_dir / "test.txt"
        filepath.write_text("hello world")

        result = await read_file(str(filepath))
        assert result["content"] == "hello world"
        assert result["size"] == 11

    async def test_read_nonexistent_file(self):
        result = await read_file("/nonexistent/file.txt")
        assert "error" in result

    async def test_read_binary_file(self, temp_dir):
        filepath = temp_dir / "data.bin"
        # 不可被 UTF-8 解码的字节序列
        filepath.write_bytes(b"\xff\xfe\x00\x00")

        result = await read_file(str(filepath))
        assert "error" in result
        assert "二进制" in result["error"]


class TestWriteFile:
    async def test_write_new_file(self, temp_dir):
        filepath = temp_dir / "new_file.py"
        result = await write_file(str(filepath), "print('hello')")

        assert result["written"] is True
        assert filepath.read_text() == "print('hello')"

    async def test_write_creates_parent_dirs(self, temp_dir):
        filepath = temp_dir / "deep" / "nested" / "file.txt"
        result = await write_file(str(filepath), "content")
        assert result["written"] is True
        assert filepath.exists()
