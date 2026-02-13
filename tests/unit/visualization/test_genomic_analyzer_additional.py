from __future__ import annotations

from pathlib import Path

from quilt_mcp.visualization.analyzers.genomic_analyzer import GenomicAnalyzer


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_detect_genomic_file_type_extension_and_content(tmp_path, monkeypatch):
    analyzer = GenomicAnalyzer()

    assert analyzer._detect_genomic_file_type(tmp_path / "a.fa") == "fasta"
    assert analyzer._detect_genomic_file_type(tmp_path / "a.fq") == "fastq"
    assert analyzer._detect_genomic_file_type(tmp_path / "a.vcf") == "vcf"
    assert analyzer._detect_genomic_file_type(tmp_path / "a.gff3") == "gtf"
    assert analyzer._detect_genomic_file_type(tmp_path / "a.bw") == "bigwig"

    content_fasta = tmp_path / "content.unknown"
    _write_text(content_fasta, ">chr1\nACGT\n")
    assert analyzer._detect_genomic_file_type(content_fasta) == "fasta"

    content_fastq = tmp_path / "content2.unknown"
    _write_text(content_fastq, "@read1\nACGT\n+\n!!!!\n")
    assert analyzer._detect_genomic_file_type(content_fastq) == "fastq"

    content_vcf = tmp_path / "content3.unknown"
    _write_text(content_vcf, "##fileformat=VCFv4.2\n")
    assert analyzer._detect_genomic_file_type(content_vcf) == "vcf"

    content_gtf = tmp_path / "content4.unknown"
    _write_text(content_gtf, "chr1\tsrc\texon\t1\t10\t.\t+\t.\tgene_id \"g1\";\n")
    assert analyzer._detect_genomic_file_type(content_gtf) == "gtf"

    unknown = tmp_path / "content5.unknown"
    _write_text(unknown, "plain text")
    assert analyzer._detect_genomic_file_type(unknown) == "unknown"

    def _open_boom(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", _open_boom)
    assert analyzer._detect_genomic_file_type(tmp_path / "binary.bam") == "bam"
    assert analyzer._detect_genomic_file_type(tmp_path / "binary.unknown") == "unknown"


def test_analyze_fasta_and_fastq_files(tmp_path):
    analyzer = GenomicAnalyzer()

    fasta = tmp_path / "sample.fa"
    _write_text(fasta, ">hg38_chr1\nACGT\n>contig2\nGGCC\n")
    fasta_analysis = analyzer._analyze_fasta_file(fasta)
    assert fasta_analysis["has_sequence_data"] is True
    assert fasta_analysis["sequence_count"] == 2
    assert fasta_analysis["total_length"] == 8
    assert fasta_analysis["average_length"] == 4
    assert fasta_analysis["gc_content"] == 0.75
    assert fasta_analysis["genome_assembly"] is None

    fastq = tmp_path / "reads.fq"
    _write_text(fastq, "@r1\nACGT\n+\n!!!!\n@r2\nGG\n+\n##\n")
    fastq_analysis = analyzer._analyze_fastq_file(fastq)
    assert fastq_analysis["has_sequence_data"] is True
    assert fastq_analysis["sequence_count"] == 2
    assert fastq_analysis["total_length"] == 6
    assert fastq_analysis["quality_scores"]["min"] <= fastq_analysis["quality_scores"]["max"]


def test_analyze_vcf_bed_gtf_and_bam(tmp_path):
    analyzer = GenomicAnalyzer()

    vcf = tmp_path / "calls.vcf"
    _write_text(
        vcf,
        "##fileformat=VCFv4.2\n"
        "##assembly=hg19\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1\n"
        "chr1\t10\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n"
        "chr2\t20\t.\tAT\tA\t.\tPASS\t.\tGT\t0/1\n"
        "chr3\t30\t.\tAA\tGG\t.\tPASS\t.\tGT\t0/1\n",
    )
    vcf_analysis = analyzer._analyze_vcf_file(vcf)
    assert vcf_analysis["has_variant_data"] is True
    assert vcf_analysis["variant_count"] == 3
    assert vcf_analysis["sample_count"] == 1
    assert set(vcf_analysis["chromosomes"]) == {"chr1", "chr2", "chr3"}
    assert set(vcf_analysis["variant_types"]) == {"SNP", "INDEL", "SUBSTITUTION"}
    assert vcf_analysis["genome_assembly"] == "hg19"

    bed = tmp_path / "regions.bed"
    _write_text(bed, "track name=t genome=mm10\nchr1\t1\t10\nchr2\t20\t30\n")
    bed_analysis = analyzer._analyze_bed_file(bed)
    assert bed_analysis["has_annotation_data"] is True
    assert bed_analysis["region_count"] == 2
    assert set(bed_analysis["chromosomes"]) == {"chr1", "chr2"}
    assert len(bed_analysis["regions"]) == 2
    assert bed_analysis["genome_assembly"] == "mm10"

    gtf = tmp_path / "genes.gtf"
    _write_text(
        gtf,
        "# genome=rn6\n"
        'chr1\tsrc\texon\t1\t100\t.\t+\t.\tgene_id "g1";\n'
        'chr1\tsrc\tgene\t5\t200\t.\t+\t.\tgene_id "g2";\n',
    )
    gtf_analysis = analyzer._analyze_gtf_file(gtf)
    assert gtf_analysis["has_annotation_data"] is True
    assert gtf_analysis["feature_count"] == 2
    assert set(gtf_analysis["feature_types"]) == {"exon", "gene"}
    assert set(gtf_analysis["genes"]) == {"g1", "g2"}
    assert gtf_analysis["genome_assembly"] == "rn6"

    bam = tmp_path / "sample_hg38.bam"
    _write_text(bam, "placeholder")
    bam_analysis = analyzer._analyze_bam_file(bam)
    assert bam_analysis["has_coverage_data"] is True
    assert bam_analysis["genome_assembly"] == "hg38"


def test_analyze_genomic_file_and_aggregate_content(tmp_path, monkeypatch):
    analyzer = GenomicAnalyzer()

    fasta = tmp_path / "one.fa"
    _write_text(fasta, ">mm10_chr1\nACGT\n")
    vcf = tmp_path / "two.vcf"
    _write_text(vcf, "##assembly=mm10\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchr1\t1\t.\tA\tG\t.\tPASS\t.\n")
    missing = tmp_path / "missing.bed"

    missing_result = analyzer._analyze_genomic_file(str(missing))
    assert missing_result is None

    def _detect_boom(_path):
        raise RuntimeError("bad file")

    monkeypatch.setattr(analyzer, "_detect_genomic_file_type", _detect_boom)
    error_result = analyzer._analyze_genomic_file(str(fasta))
    assert error_result is not None and "error" in error_result

    monkeypatch.undo()
    aggregate = analyzer.analyze_genomic_content([str(fasta), str(vcf), str(missing)])
    assert aggregate["genomic_file_count"] == 3
    assert aggregate["has_sequence_data"] is True
    assert aggregate["has_variant_data"] is True
    assert aggregate["genome_assembly"] == "mm10"
    assert isinstance(aggregate["chromosomes"], list)
    assert "biological_context" in aggregate


def test_context_recommendations_suggestions_and_summary():
    analyzer = GenomicAnalyzer()

    analysis = {
        "genomic_file_count": 12,
        "genome_assembly": "hg38",
        "has_sequence_data": True,
        "has_variant_data": True,
        "has_annotation_data": True,
        "has_coverage_data": True,
        "chromosomes": ["chr1", "chr2"],
    }

    context = analyzer._determine_biological_context(analysis)
    assert context["organism"] == "Human"
    assert context["data_type"] == "Sequencing Data"
    assert context["analysis_type"] == "Variant Analysis"
    assert context["complexity"] == "High"

    recs = analyzer._generate_recommendations(analysis)
    assert len(recs) >= 4

    suggestions = analyzer._suggest_visualizations(analysis)
    assert "variant_view" in suggestions
    assert "coverage_plot" in suggestions
    assert "genome_track" in suggestions
    assert "sequence_view" in suggestions
    assert "multi_chromosome_view" in suggestions

    no_assembly_recs = analyzer._generate_recommendations({"has_sequence_data": True})
    assert any("Genome assembly information" in r for r in no_assembly_recs)

    summary = analyzer.get_genomic_summary([])
    assert "summary" in summary
    assert "recommendations" in summary
    assert "visualization_suggestions" in summary
