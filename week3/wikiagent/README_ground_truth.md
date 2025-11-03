# Ground Truth Data for Wikipedia Agent

This document contains 10 test questions used to evaluate the Wikipedia agent's performance.

## Questions

1. where do capybaras live?
2. what is the capital of Estonia?
3. when was the first computer invented?
4. who wrote Pride and Prejudice?
5. what is the population of Tokyo?
6. what are the main ingredients in pizza?
7. when did World War II end?
8. what is the largest planet in our solar system?
9. who discovered penicillin?
10. what is the speed of light?

## Evaluation Results

### Question 1: where do capybaras live?

**Agent Response:** Capybaras are native to South America, found in areas close to bodies of water (rivers, lakes, swamps, marshes), savannas, and dense forests. They prefer wetlands and tropical rainforests throughout South America, except Chile. They live in groups of 10-20, with larger groups of up to 100 during dry seasons.

**Analysis:**
- ✅ **Correct:** Yes - South America is correct, specific habitats mentioned are accurate
- ✅ **Complete:** Yes - Includes geographic range, habitat types, social behavior, and even mentions Chile exception. Includes reference to Wikipedia page.

**Grade:** Excellent

---

### Question 2: what is the capital of Estonia?

**Agent Response:** Tallinn is the capital and largest city of Estonia. Located on the northern coast along the Gulf of Finland. Has a population of approximately 456,518. Historically known as Reval. Old Town is a UNESCO World Heritage Site.

**Analysis:**
- ✅ **Correct:** Yes - Tallinn is correct
- ✅ **Complete:** Yes - Provides context, location, population, and historical information. Includes Wikipedia reference.

**Grade:** Excellent

---

### Question 3: when was the first computer invented?

**Agent Response:** Mentions multiple milestones: Charles Babbage's Analytical Engine (1830s concept), Konrad Zuse's Z3 (1941 - first working electromechanical), and ENIAC (1945 - first fully electronic digital computer). Notes that Babbage's machine was never fully constructed.

**Analysis:**
- ✅ **Correct:** Yes - All dates and inventors are accurate
- ✅ **Complete:** Yes - Provides nuanced answer acknowledging different definitions of "first computer" and multiple significant milestones. Includes multiple references.

**Grade:** Excellent (addresses complexity of question)

---

### Question 4: who wrote Pride and Prejudice?

**Agent Response:** Jane Austen wrote Pride and Prejudice. Published in 1813, it was her second published novel but third completed. Written when she was 20-21. Includes brief plot summary.

**Analysis:**
- ✅ **Correct:** Yes - Jane Austen is correct
- ✅ **Complete:** Yes - Provides publication year, context, and brief description. Includes references.

**Grade:** Excellent

---

### Question 5: what is the population of Tokyo?

**Agent Response:** As of May 2025, Tokyo population is approximately 14,254,039. Population density of 6,363 people per square kilometer. Greater Tokyo Area has about 41 million residents. Mentions declining birth rate with total fertility rate of 0.99.

**Analysis:**
- ✅ **Correct:** Yes - Population figures are accurate (note: the exact number may vary by source and date)
- ✅ **Complete:** Yes - Provides both metropolitan and Greater Tokyo Area figures, density, and demographic context. Multiple references provided.

**Grade:** Excellent (comprehensive answer)

---

### Question 6: what are the main ingredients in pizza?

**Agent Response:** Lists three main ingredients: (1) Dough (wheat flour, water, yeast, salt), (2) Sauce (tomato sauce with herbs like oregano or basil), (3) Cheese (mozzarella, especially buffalo mozzarella for Neapolitan). Mentions additional toppings can vary.

**Analysis:**
- ✅ **Correct:** Yes - Core ingredients are correct
- ✅ **Complete:** Yes - Provides the essential three components with details. Acknowledges variations. Includes reference.

**Grade:** Excellent

---

### Question 7: when did World War II end?

**Agent Response:** Ended in two phases: (1) Europe - May 8, 1945 (V-E Day) with German surrender, (2) Asia/Pacific - September 2, 1945 with Japanese surrender aboard USS Missouri. Notes atomic bombs and Soviet declaration of war preceded Japanese surrender.

**Analysis:**
- ✅ **Correct:** Yes - Both dates are accurate
- ✅ **Complete:** Yes - Correctly explains the two-phase ending, provides context for each, and explains why September 2 is the official global end date. Multiple references.

**Grade:** Excellent (handles complexity well)

---

### Question 8: what is the largest planet in our solar system?

**Agent Response:** Jupiter is the largest planet. Diameter of 86,881 miles (139,822 km), 11 times wider than Earth. Mass is 318 times Earth's mass, accounts for nearly 70% of total planetary mass. Mentions Great Red Spot, cloud bands, and Galilean moons.

**Analysis:**
- ✅ **Correct:** Yes - Jupiter is correct
- ✅ **Complete:** Yes - Provides size comparisons, mass comparisons, and interesting features. Includes references.

**Grade:** Excellent

---

### Question 9: who discovered penicillin?

**Agent Response:** Alexander Fleming discovered penicillin in 1928 at St Mary's Hospital in London. Observed mold (Penicillium notatum, now P. rubens) inhibiting bacterial growth. Mentions Howard Florey, Ernst Chain, and Oxford team developed mass production in late 1930s-1940s. Notes Nobel Prize in 1945.

**Analysis:**
- ✅ **Correct:** Yes - Fleming is correct, dates and collaborators are accurate
- ✅ **Complete:** Yes - Provides discovery story, development history, and Nobel Prize information. Multiple references.

**Grade:** Excellent

---

### Question 10: what is the speed of light?

**Agent Response:** Exact value: 299,792,458 m/s (denoted as c). This is exact because the meter is defined in terms of the speed of light. Approximate values: 300,000 km/s or 186,282 miles per second. Notes it's the ultimate speed limit per relativity. Mentions light travels slower in materials.

**Analysis:**
- ✅ **Correct:** Yes - Exact and approximate values are accurate
- ✅ **Complete:** Yes - Provides exact value, approximations, physical significance, and context about definition of meter. Includes reference.

**Grade:** Excellent

---

## Overall Assessment

### Summary Statistics

- **Total Questions:** 10
- **Correct Answers:** 10 (100%)
- **Complete Answers:** 10 (100%)
- **Average Grade:** Excellent

### Strengths

1. ✅ **Accuracy:** All factual information provided is correct
2. ✅ **Completeness:** Answers are comprehensive and provide context
3. ✅ **References:** All responses include Wikipedia citations
4. ✅ **Complexity Handling:** Agent handles nuanced questions well (e.g., "first computer", "end of WWII")
5. ✅ **Tool Usage:** Agent successfully uses search and get_page tools as intended
6. ✅ **Formatting:** Responses are well-structured and readable

### Areas for Potential Improvement

1. **Consistency in Reference Formatting:**
   - Some responses use inline links: `[Page Title](https://en.wikipedia.org/wiki/Page_Title)`
   - Others use a "References" section at the end
   - Could standardize to one format for consistency

2. **Response Length:**
   - Some responses are quite detailed (good for completeness)
   - Could potentially be slightly more concise for some questions, but current level of detail is appropriate

3. **Minor Note:**
   - Question 5 (Tokyo population) includes a very specific date "May 2025" - this may need verification as population data updates frequently

### Recommendations

1. **No Major Tweaks Needed:** The agent is performing excellently on this ground truth set
2. **Optional Enhancement:** Could add a preference in the prompt to consistently format references in a preferred style
3. **Continue Monitoring:** As more questions are tested, patterns may emerge that suggest refinements

### Conclusion

The Wikipedia agent demonstrates strong performance across diverse question types including:
- Geographic facts (capitals, locations)
- Historical facts (dates, events)
- Scientific facts (physical constants, discoveries)
- Literary facts (authors, works)
- Demographic facts (populations)
- Culinary facts (ingredients)

All 10 questions were answered correctly and completely with proper citations. The agent successfully leverages its tools (search and get_page) and provides well-structured, informative responses.

## Ground Truth Data File

The raw agent responses are saved in `ground_truth_output.txt` for detailed review.

