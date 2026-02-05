from pathlib import Path

from quilt_mcp.visualization.analyzers.genomic_analyzer import GenomicAnalyzer


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_analyze_genomic_content_detects_assembly(tmp_path):
    fasta_path = tmp_path / "sample.fasta"
    _write_text(fasta_path, ">hg38_chr1\nACGTACGT\n")

    vcf_path = tmp_path / "sample.vcf"
    _write_text(
        vcf_path,
        "##fileformat=VCFv4.2\n##assembly=hg38\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t100\t.\tA\tG\t.\tPASS\t.\n",
    )

    analyzer = GenomicAnalyzer()
    analysis = analyzer.analyze_genomic_content([str(fasta_path), str(vcf_path)])

    assert analysis["genomic_file_count"] == 2
    assert analysis["has_sequence_data"] is True
    assert analysis["has_variant_data"] is True
    assert analysis["genome_assembly"] == "hg38"
