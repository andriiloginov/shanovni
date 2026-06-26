from pathlib import Path

UA = {'User-Agent': 'Shanovni/1.0'}

CITIES = {
    "kyiv": {
        "name": "Київська міська рада",
        "deputies_url": "https://data.gov.ua/dataset/65e266f5-53e9-4775-afd8-55fba3359a54/resource/bbd7e08a-7487-45dd-b5db-f4a35caed549/download/deputaty-kmr.xlsx",
        "voting_quarters": {
            "IV квартал 2025": "https://data.gov.ua/dataset/11dc30c6-6cbf-4f63-ab92-ebb156a7a689/resource/e051ac02-2688-4f69-8415-8c61ac10e1c8/download/09-10-2025-rezultati-poimennikh-golosuvan-strukturoвані-дані.zip",
        },
        "council_decisions": {
            "2025_h2": "https://data.gov.ua/dataset/e404f7ac-ea9c-468f-8a20-e7dda235feb5/resource/a4c084fe-2928-43ec-9ac1-0a5d3e09250c/download/rishennia-kmr-ii-pivrichchia-2025-roku-xlsx.xlsx",
        },
        "salaries_url": "https://data.gov.ua/dataset/0272e07e-53f7-4a93-ab21-5a227c6ca59c/resource/3e2a162b-ab41-421a-9cb0-c83c51e1db46/download/salaries.csv",
        "petitions_url": "https://data.kyivcity.gov.ua/dataset/2c6f7b60-4956-41a5-ba81-1a00aa87f3ec/resource/be62b7cf-cbfb-4b2f-8235-e51594fa910f/download/petitions.json",
    },
}

SALARY_COMPONENTS = {
    "basePay": "Оклад",
    "seniorityAllowance": "Вислуга років",
    "laborIntensityAllowance": "Інтенсивність праці",
    "benefits": "Премія",
    "vacation": "Відпустка основна",
    "vacationAdditional": "Відпустка додаткова",
    "vacationChildren": "Відпустка на дітей",
    "UnusedVacationCompensation": "Компенсація відпустки",
    "socialAssistance": "Матеріальна допомога",
    "assistanceHealthImprovement": "Допомога на оздоровлення",
    "averagePayBusinessTrip": "Відрядження",
    "averagePayBloodDonor": "Донорство",
    "indexation": "Індексація",
    "sickLeaves": "Лікарняні",
    "sickLeavesPfu": "Лікарняні ПФУ",
    "otherPay": "Інше",
}

ASSISTANT_SYSTEM_PROMPT = Path("prompts/assistant.md").read_text(encoding="utf-8").format(
    council_name=CITIES["kyiv"]["name"]
)

CHAT_FAST_MODE = False  # False → claude-haiku-4-5, True → claude-opus-4-8 fast (потребує доступу)

NAZK_API = "http://api.shanovni.org/proxy.php"
NAZK_PUBLIC = "https://public.nazk.gov.ua/documents"
