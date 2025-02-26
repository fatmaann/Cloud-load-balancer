# Cloud-load-balancer

---

## Логброкер с ClickHouse и Nginx в Yandex Cloud

Этот проект представляет собой инфраструктурный сервис для сбора, буферизации и доставки логов в ClickHouse с использованием Nginx в качестве балансировщика запросов. Основная цель — создать масштабируемое и отказоустойчивое решение для работы с логами в облачной среде. Процесс развертывания и управления инфраструктурой автоматизирован с помощью Terraform, а логика работы сервиса реализована с учетом принципов cloud-native.

---

## Требования к реализации

- **Персистентная буферизация:**
  - Логи сохраняются на диск перед отправкой в ClickHouse.
  - Гарантируется доставка всех логов даже после перезапуска сервиса.

- **Ограничение на частоту запросов:**
  - Запросы в ClickHouse отправляются не чаще раза в секунду.

- **Изоляция сети:**
  - База данных и бэкенд-сервисы доступны только через внутреннюю сеть.
  - NAT-инстанс обеспечивает доступ в интернет для машин без публичных IP.

## Архитектура решения

Проект включает следующие компоненты:

1. **Nginx (Балансировщик запросов):**
   - Равномерно распределяет входящие запросы между несколькими бэкенд-сервисами.
   - Единственный компонент, доступный извне.

2. **Бэкенд-сервисы:**
   - Принимают логи через API, буферизируют их на диск и отправляют в ClickHouse батчами (не чаще раза в секунду).
   - Гарантируют доставку всех логов даже после перезапуска сервиса.

3. **ClickHouse (База данных):**
   - Используется для хранения структурированных логов.
   - Настроен в контейнере с простой таблицей для логов.

4. **NAT-инстанс:**
   - Обеспечивает доступ в интернет для машин без публичных IP-адресов.
   - Используется как jump-хост для деплоя и управления инфраструктурой.

5. **Сеть:**
   - Все компоненты развернуты в изолированной подсети.
   - База данных и бэкенд-сервисы доступны только через внутреннюю сеть.

## Основные этапы работы

### **Сборка и загрузка Docker-образов**
   - Бэкенд-сервис и ClickHouse упакованы в Docker-образы.
   - Образы загружаются в Yandex Container Registry для использования в облаке.

### **Развертывание инфраструктуры с помощью Terraform**
   - Создаются виртуальные машины для Nginx, бэкенд-сервисов и ClickHouse.
   - Настраиваются сетевые правила и security groups для изоляции компонентов.
   - Развертывается NAT-инстанс для доступа в интернет.

### **Настройка Nginx**
   - Nginx конфигурируется как балансировщик запросов между бэкенд-сервисами.
   - Обеспечивается доступ только к Nginx извне.

### **Запуск бэкенд-сервисов**
   - Сервисы принимают логи через API, буферизируют их на диск и отправляют в ClickHouse батчами.
   - Реализована обработка shutdown event для гарантированной доставки логов при остановке сервиса.

### **Настройка ClickHouse**
   - Создается таблица для хранения логов.
   - Настраивается конфигурация для оптимальной работы с большими объемами данных.

### **Автоматизация через CI/CD**
   - Процесс сборки, тестирования и развертывания автоматизирован с помощью GitLab CI/CD.
   - При пуше изменений в репозиторий:
     - Собираются Docker-образы.
     - Образы загружаются в Yandex Container Registry.
     - Запускаются Terraform и Ansible для развертывания инфраструктуры.

## Технологии

- **Фреймворки:**
  - FastAPI (для бэкенд-сервиса)
  - ClickHouse (для хранения логов)
  - Nginx (для балансировки запросов)

- **Инфраструктура:**
  - Yandex Cloud
  - Terraform (для управления инфраструктурой)
  - Docker (для контейнеризации)

- **Автоматизация:**
  - Ansible (для настройки виртуальных машин)