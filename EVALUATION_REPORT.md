# Agentic AI Engineering — Assignment 1: Evaluation Report

**Course:** PGDM (Big Data Analytics / AI & Data Science)  
**Batch:** 2025–27  
**Assignment:** Intelligent Student Support Agent  
**Evaluation Date:** October 2026  
**Status:** Evaluated and Verified

---

## 1. Tracing and Measurement

The agent was evaluated against the five demonstration scenarios specified in the assignment brief.

| Scenario | Test Case | Status | Tools Used & Assessment | Latency | Input Tokens | Output Tokens | Total Tokens |
|---|---|---|---|---:|---:|---:|---:|
| 1 | Current fee status | PASS | check_fee_status (Appropriate) | 2.072s | 1858 | 542 | 2400 |
| 2 | Payment portal failure | PASS | check_fee_status (Review) | 2.368s | 1858 | 695 | 2553 |
| 3 | Persistent memory recall | PASS | Direct / RAG (No tool) | 2.162s | 944 | 786 | 1730 |
| 4 | Sensitive and temporary information | PASS | Direct / RAG (No tool) | 1.287s | 937 | 271 | 1208 |
| 5 | Insufficient policy information | PASS | Direct / RAG (No tool) | 2.887s | 899 | 258 | 1157 |

---

## 2. Aggregate Performance Metrics

| Performance Metric | Result |
|---|---:|
| Task Accuracy | 100% (5/5 scenarios passed) |
| Mean End-to-End Latency | 2.16 seconds |
| Total Input Tokens | 6,496 |
| Total Output Tokens | 2,552 |
| Total Tokens Consumed | 9,048 |

**Mean Latency Calculation:**

(2.072 + 2.368 + 2.162 + 1.287 + 2.887) / 5 = 2.1552 seconds

Rounded mean latency = 2.16 seconds.

---

## 3. Detailed Scenario Observations

### Scenario 1: Fee Status Query

**Question:** "What is my current fee status?"

**Result:** PASS

**Tool Used:** check_fee_status

The agent successfully invoked the fee-status tool and retrieved the student's fee information, including paid amount and outstanding balance.

**Latency:** 2.072 seconds  
**Total Tokens:** 2,400

### Scenario 2: Payment Portal Failure

**Question:** "The payment portal failed. Can I pay on the next working day?"

**Result:** PASS

**Tool Used:** check_fee_status (Review)

The agent retrieved relevant handbook information concerning payment portal failures and grace-period policies. The fee-status tool was also invoked, although its selection was not ideal for the primary policy question.

**Retrieved Evidence:** POLICY-SEC-4 and POLICY-SEC-3.

**Latency:** 2.368 seconds  
**Total Tokens:** 2,553

### Scenario 3: Persistent Memory Across Sessions

**Question:** "What electives do you recommend for me?"

**Result:** PASS

**Tool Used:** None (Direct / RAG)

The agent successfully accessed previously stored student preference information and used the specialization_interest memory to provide a relevant response.

**Retrieved Evidence:** Memory: specialization_interest.

**Latency:** 2.162 seconds  
**Total Tokens:** 1,730

### Scenario 4: Sensitive and Temporary Information Filter

**Question:** A test statement containing a student portal password and temporary health-related information.

**Result:** PASS

**Tool Used:** None (Direct / RAG)

The scenario passed the sensitive and temporary information filtering test.

A separate verification of the execution trace confirmed that the exact test password and sensitive question were absent from the trace log after sanitization.

**Latency:** 1.287 seconds  
**Total Tokens:** 1,208

### Scenario 5: Policy Gap Handling

**Question:** "Does the institute provide a monthly financial allowance or subsidy for off-campus private hostel rent?"

**Result:** PASS

**Tool Used:** None (Direct / RAG)

The agent handled the question for which sufficient policy information was unavailable, demonstrating policy-gap handling without an unnecessary tool invocation.

**Latency:** 2.887 seconds  
**Total Tokens:** 1,157

---

## 4. Additional Assignment 2 Enhancements

Beyond the original Assignment 1 requirements, the implementation includes:

1. Student ownership checks for data-access tools.
2. Audit logging for tool access and authorization decisions.
3. Fee-waiver request submission.
4. Human approval and rejection workflow.
5. Separate recording of fee-waiver adjustments and payments.
6. Sensitive-information sanitization in execution traces.

The approval and student identity controls are demonstration-level mechanisms and do not represent production-grade authentication.

---

## 5. Key Observations and Limitations

- All five predefined evaluation scenarios passed.
- The fee-status tool was correctly used for the fee-status query.
- The payment portal scenario retrieved relevant policy evidence, although tool selection should be improved.
- Persistent memory successfully retrieved previously stored student preferences.
- Sensitive test information was not found in the sanitized execution trace.
- The policy-gap scenario passed without a tool call.

The reported 100% accuracy applies only to the five predefined demonstration scenarios and should not be interpreted as production-level reliability.

---

## 6. Conclusion

The Intelligent Student Support Agent successfully demonstrates agentic decision-making, tool integration, retrieval-augmented generation, persistent memory, context selection, and execution tracing.

The additional implementation extends the system with authorization checks, audit logging, sensitive-information sanitization, and a human approval workflow.

The evaluation results demonstrate successful execution of all five predefined assignment scenarios.

