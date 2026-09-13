# Data License

The dataset used in this project is `anudit/rajyasabha-qa` on Hugging Face, licensed under **MIT License**.

## Dataset Terms

- **Repository:** `anudit/rajyasabha-qa`
- **Revision:** `508b2411283162fdd52ee2c3e8ccaefbabfe9581`
- **License:** MIT
- **Size:** 306,400 rows, 509 MB parquet
- **Access:** Public, no token required

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## TCPD Clause (if member/minister tables kept)

If derived tables containing member codes (`mp_code`) or minister names are retained in outputs,
note that these may constitute personal data under applicable privacy laws. This project
does not store or distribute such derived tables — only the original corpus fields are used
for retrieval and citation. If you extend this work to include member/minister analytics,
consult the original data provider and applicable regulations (e.g., DPDP Act 2023).

## Provenance

- Source: Rajya Sabha Secretariat official publications
- Compilation: Anudit (Hugging Face user)
- Coverage: 1995–2024 parliamentary sessions
- Languages: English (primary), Hindi (23.6% of rows)
- Fields: 15 columns including question text, answer text, ministry, session, date, status, member

## Citation

If you use this dataset, please cite:
```
@dataset{rajyasabha_qa,
  title = {Rajya Sabha Question-Answer Corpus},
  author = {Anudit},
  year = {2024},
  publisher = {Hugging Face},
  url = {https://huggingface.co/datasets/anudit/rajyasabha-qa}
}
```