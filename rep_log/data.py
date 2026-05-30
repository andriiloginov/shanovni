UA = {'User-Agent': 'Shanovni/1.0'}

# Список депутатів Київради (Excel)
DEPUTIES_URL = "https://data.gov.ua/dataset/65e266f5-53e9-4775-afd8-55fba3359a54/resource/bbd7e08a-7487-45dd-b5db-f4a35caed549/download/deputaty-kmr.xlsx"

# ZIP-архіви поіменних голосувань за кварталами (JSON-файли всередині)
VOTING_QUARTERS = {
    "IV квартал 2025": "https://data.gov.ua/dataset/11dc30c6-6cbf-4f63-ab92-ebb156a7a689/resource/e051ac02-2688-4f69-8415-8c61ac10e1c8/download/09-10-2025-rezultati-poimennikh-golosuvan-strukturoвані-дані.zip",
}

# Зарплати керівництва КМДА (CSV)
SALARIES_URL = "https://data.gov.ua/dataset/0272e07e-53f7-4a93-ab21-5a227c6ca59c/resource/3e2a162b-ab41-421a-9cb0-c83c51e1db46/download/salaries.csv"

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
