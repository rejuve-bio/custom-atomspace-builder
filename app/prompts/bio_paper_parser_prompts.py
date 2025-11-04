def get_system_prompt() -> str:
    return (
        "You are a biomedical knowledge graph extractor. "
        "Given text from biological or biomedical research papers, identify key factual or causal statements "
        "and represent them as logical triples in METTA/Hyperon FOL format. "
        "Each triple must capture a clear biological or experimental relationship among entities such as "
        "genes, proteins, cells, pathways, species, molecules, diseases, phenotypes, experimental methods, "
        "observations, or computational models. "
        "Use expressive, domain-aware predicates such as regulates, activates, inhibits, interacts_with, "
        "involves, associates_with, expresses, measures, increases, decreases, modulates, causes, prevents, "
        "predicts, supports, demonstrates, or indicates. "
        "Avoid vague or linguistic relations — express concrete biological semantics. "
        "Output ONLY the triples, no explanations, exactly one per line, in (subject predicate object) format."
    )


def build_prompt(text_chunk: str) -> str:
    return f"""
Extract broad biological and biomedical relationships from the following text.
Represent each finding, interaction, or observation as a logical triple suitable for a knowledge graph
in METTA/Hyperon First-Order Logic format.

Include relationships from:
- Molecular biology (gene, protein, metabolite)
- Cell biology (organelle, signal, function)
- Physiology and anatomy (organ, tissue, response)
- Ecology and evolution (species, population, adaptation)
- Computational biology and bioinformatics (algorithm, dataset, prediction)
- Medicine and health (disease, drug, biomarker, effect)
- Experimental context (method, assay, result)

Each triple must follow:
(subject predicate object)

Example:
(TP53 regulates apoptosis)
(CRISPR_Cas9 enables targeted_gene_editing)
(Metabolic_stress activates AMPK_pathway)
(Deep_learning_model predicts protein_structure)
(Mutation_in_BRCA1 increases cancer_risk)
(Antibody_binding inhibits viral_entry)
(Cellular_differentiation involves transcription_factor_SOX2)

Text:
{text_chunk}

Output only the FOL triples:
(subject predicate object)
(subject predicate object)
...
"""