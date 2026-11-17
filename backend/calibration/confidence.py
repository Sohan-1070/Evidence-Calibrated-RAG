def calculate_confidence(
    evidence,
    verification_results
):
    """
    Calculate an initial evidence confidence score.

    Signals:
    1. Retrieval relevance
    2. Evidence coverage
    3. Claim support
    4. Contradiction
    5. Cross-document agreement
    6. Source reliability
    """

    # --------------------------------------------------
    # 1. RETRIEVAL RELEVANCE
    # --------------------------------------------------

    if evidence:

        retrieval_scores = [
            item["score"]
            for item in evidence
        ]

        retrieval_relevance = sum(
            retrieval_scores
        ) / len(
            retrieval_scores
        )

    else:

        retrieval_relevance = 0.0


    # --------------------------------------------------
    # 2. EVIDENCE COVERAGE
    # --------------------------------------------------

    total_claims = len(
        verification_results
    )

    if total_claims == 0:

        evidence_coverage = 0.0

    else:

        supported_claims = sum(
            1
            for result in verification_results
            if result["verdict"] == "SUPPORTED"
        )

        evidence_coverage = (
            supported_claims /
            total_claims
        )


    # --------------------------------------------------
    # 3. CLAIM SUPPORT
    # --------------------------------------------------

    if total_claims == 0:

        claim_support = 0.0

    else:

        claim_support = (
            sum(
                1
                for result in verification_results
                if result["verdict"] == "SUPPORTED"
            )
            /
            total_claims
        )


    # --------------------------------------------------
    # 4. CONTRADICTION
    # --------------------------------------------------

    if total_claims == 0:

        contradiction_score = 0.0

    else:

        contradicted_claims = sum(
            1
            for result in verification_results
            if result["verdict"] == "CONTRADICTED"
        )

        contradiction_score = (
            contradicted_claims /
            total_claims
        )


    # --------------------------------------------------
    # 5. CROSS-DOCUMENT AGREEMENT
    # --------------------------------------------------

    pages = set(
        item["page"]
        for item in evidence
    )

    if len(pages) >= 1:
        cross_document_agreement = 1.0
    else:
        cross_document_agreement = 0.0

    # --------------------------------------------------
    # 6. SOURCE RELIABILITY
    # --------------------------------------------------

    # For our current prototype, the PDF is treated
    # as a known source.

    if evidence:
        source_reliability = 1.0
    else:
        source_reliability = 0.0

    # --------------------------------------------------
    # FINAL CONFIDENCE
    # --------------------------------------------------

    # When all extracted claims are fully supported by the document with 0 contradictions:
    if total_claims > 0 and supported_claims == total_claims and contradiction_score == 0.0 and evidence:
        confidence = 1.0
    else:
        confidence = (
            0.20 * retrieval_relevance
            + 0.20 * evidence_coverage
            + 0.25 * claim_support
            + 0.15 * (1 - contradiction_score)
            + 0.10 * cross_document_agreement
            + 0.10 * source_reliability
        )


    # Keep score between 0 and 1

    confidence = max(
        0.0,
        min(
            1.0,
            confidence
        )
    )


    return {

        "confidence": confidence,

        "retrieval_relevance":
            retrieval_relevance,

        "evidence_coverage":
            evidence_coverage,

        "claim_support":
            claim_support,

        "contradiction":
            contradiction_score,

        "cross_document_agreement":
            cross_document_agreement,

        "source_reliability":
            source_reliability
    }


if __name__ == "__main__":

    test_evidence = [

        {
            "page": 3,
            "score": 0.85,
            "text": "Standard forms are used for employee administrative functions."
        },

        {
            "page": 5,
            "score": 0.80,
            "text": "Time-off requests use standard forms."
        }

    ]


    test_results = [

        {
            "claim": "The council uses standard forms.",
            "verdict": "SUPPORTED",
            "reason": "Evidence supports the claim."
        },

        {
            "claim": "The council uses standard forms for time-off requests.",
            "verdict": "SUPPORTED",
            "reason": "Evidence supports the claim."
        }

    ]


    result = calculate_confidence(
        test_evidence,
        test_results
    )


    print("\nEVIDENCE CONFIDENCE")
    print("=" * 50)

    print(
        f"Final confidence: "
        f"{result['confidence']:.3f}"
    )

    print(
        f"Retrieval relevance: "
        f"{result['retrieval_relevance']:.3f}"
    )

    print(
        f"Evidence coverage: "
        f"{result['evidence_coverage']:.3f}"
    )

    print(
        f"Claim support: "
        f"{result['claim_support']:.3f}"
    )

    print(
        f"Contradiction: "
        f"{result['contradiction']:.3f}"
    )

    print(
        f"Cross-document agreement: "
        f"{result['cross_document_agreement']:.3f}"
    )

    print(
        f"Source reliability: "
        f"{result['source_reliability']:.3f}"
    )