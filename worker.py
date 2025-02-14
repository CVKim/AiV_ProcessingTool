# worker.py
import os
import shutil
import logging
import random
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtCore import QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from datetime import datetime

logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def set_worker_priority():
    try:
        import win32api, win32process, win32con
        thread_handle = win32api.GetCurrentThread()
        # THREAD_PRIORITY_BELOW_NORMAL이나 THREAD_PRIORITY_LOWEST 등으로 설정 가능
        win32process.SetThreadPriority(thread_handle, win32process.THREAD_PRIORITY_BELOW_NORMAL)
    except ImportError:
        try:
            os.nice(10) # default 0, range -20 ~ 19
        except Exception:
            pass
        
class WorkerThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    ng_count_result = pyqtSignal(list)
    finished = pyqtSignal(str)

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._is_stopped = False
        self.max_workers = min(8, (multiprocessing.cpu_count() or 1) * 2)

    def run(self):
        try:
            operation = self.task.get('operation', '')
            if operation == 'ng_sorting':
                self.ng_folder_sorting(self.task)
            elif operation == 'date_copy':
                self.date_based_copy(self.task)
            elif operation == 'image_copy':
                self.image_format_copy(self.task)
            elif operation == 'simulation_foldering':
                self.simulation_foldering(self.task)
            elif operation == 'ng_count':
                self.ng_count(self.task)
            elif operation == 'basic_sorting':
                self.basic_sorting(self.task)
            elif operation == 'crop':
                self.crop_images(self.task)
            # ------------------ 새로 추가된 작업들 ------------------
            elif operation == 'attach_fov':
                self.attach_fov(self.task)
            elif operation == 'mim_to_bmp':
                self.mim_to_bmp(self.task)
            elif operation == 'temp':
                self.temp_operation(self.task)
            # -----------------------------------------------------
            else:
                self.log.emit("알 수 없는 작업 유형입니다.")
                self.finished.emit("알 수 없는 작업 유형입니다.")
        except Exception as e:
            logging.error("작업 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중 오류 발생했습니다.")

    def stop(self):
        self._is_stopped = True

    def ng_folder_sorting(self, task):
        self.log.emit("------ NG Folder Sorting 작업 시작 ------")
        try:
            # Task 딕셔너리에서 필요한 정보 추출
            sources1 = task.get('inputs', [])  # List of NG folder paths
            source2 = task.get('source2', '')   # Matching Inner ID folder path
            target = task.get('target', '')     # Target directory
            formats = task.get('formats', [])   # List of selected image formats

            # 입력 값 로그 출력
            self.log.emit(f"Sources1: {sources1}")
            self.log.emit(f"Source2: {source2}")
            self.log.emit(f"Target: {target}")
            self.log.emit(f"Formats: {formats}")

            # Target 디렉토리 존재 여부 확인 및 생성 (최상위 target 폴더는 미리 생성)
            if not os.path.exists(target):
                try:
                    os.makedirs(target)
                    self.log.emit(f"Target 디렉토리 생성: {target}")
                except Exception as e:
                    self.log.emit(f"Target 디렉토리 생성 실패: {target} | 에러: {e}")
                    self.finished.emit("NG Folder Sorting 완료.")
                    return
            else:
                self.log.emit(f"Target 디렉토리 존재: {target}")

            # sources1에서 inner ID(폴더 이름)만 추출하고, source2 내의 inner ID 폴더와 교집합 계산
            inner_ids_sources1 = self.collect_inner_ids(sources1)
            inner_ids_source2 = self.collect_inner_ids_from_source2(source2)
            matched_inner_ids = inner_ids_sources1.intersection(inner_ids_source2)

            total_matched_inner_ids = len(matched_inner_ids)
            if total_matched_inner_ids == 0:
                self.log.emit("sources1과 source2 모두에 존재하는 Inner ID가 없습니다.")
                self.finished.emit("NG Folder Sorting 완료.")
                return
            self.log.emit(f"총 매칭된 Inner ID 수: {total_matched_inner_ids}")

            # (기존에는 미리 target 폴더를 생성했으나, 아래에서 복사 시점에 폴더 생성)

            images_to_copy, total_images = self.collect_images_to_copy(matched_inner_ids, source2, formats)

            if total_images == 0:
                self.log.emit("선택한 이미지 포맷에 해당하는 이미지가 없습니다.")
                self.finished.emit("NG Folder Sorting 완료.")
                return
            self.log.emit(f"총 복사할 이미지 수: {total_images}")

            total_processed_images = 0

            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = {}
                for inner_id, images in images_to_copy.items():
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return

                    source_inner_id_folder = os.path.join(source2, inner_id)
                    target_inner_id_folder = os.path.join(target, inner_id)

                    # 복사 시점에 target 폴더가 없으면 생성
                    if not os.path.exists(target_inner_id_folder):
                        try:
                            os.makedirs(target_inner_id_folder)
                            self.log.emit(f"Target 폴더 생성: {target_inner_id_folder}")
                        except Exception as e:
                            self.log.emit(f"Target 폴더 생성 실패: {target_inner_id_folder} | 에러: {e}")
                            continue

                    for image in images:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                            return

                        src_file = os.path.join(source_inner_id_folder, image)
                        dst_file = os.path.join(target_inner_id_folder, image)

                        if os.path.exists(dst_file):
                            self.log.emit(f"파일이 이미 존재하여 건너뜁니다: {dst_file}")
                            continue

                        futures[executor.submit(self.copy_file, src_file, dst_file)] = (src_file, dst_file)

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return

                    result = future.result()
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        total_processed_images += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))

            self.finished.emit(f"NG Folder Sorting 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ NG Folder Sorting 작업 완료 ------")
        except Exception as e:
            logging.error("NG Folder Sorting 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("NG Folder Sorting 중 오류 발생.")

    def date_based_copy(self, task):
        self.log.emit("------ Date-Based Copy 작업 시작 ------")
        try:
            mode = task.get('mode', 'folder')
            source = task['source']
            target = task['target']
            count = task['count']
            formats = task.get('formats', [])
            specified_datetime = datetime(task['year'], task['month'], task['day'],
                                          task['hour'], task['minute'], task['second'])
            strong_random = task.get('strong_random', False)
            conditional_random = task.get('conditional_random', False)
            random_count = task.get('random_count', 0)
            fov_numbers = task.get('fov_numbers', [])

            if not os.path.exists(source):
                self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                self.finished.emit("Date-Based Copy 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            # 모든 폴더 수집 및 날짜 필터 적용
            all_folders = [os.path.join(source, f) for f in os.listdir(source) if os.path.isdir(os.path.join(source, f))]
            eligible_folders = []
            for folder in all_folders:
                try:
                    folder_mtime = datetime.fromtimestamp(os.path.getmtime(folder))
                    if folder_mtime >= specified_datetime:
                        eligible_folders.append(folder)
                except Exception as e:
                    self.log.emit(f"폴더 {folder}의 수정 시간 확인 중 오류: {str(e)}")
            if not eligible_folders:
                self.log.emit("지정된 날짜 이후의 폴더가 없습니다.")
                self.finished.emit("Date-Based Copy 완료.")
                return

            # 날짜 기준 정렬 (오름차순)
            sorted_folders = sorted(eligible_folders, key=lambda x: os.path.getmtime(x))

            if mode == 'folder':
                if strong_random:
                    self.log.emit("Strong Random 옵션 선택됨 (Folder Mode)")
                    if len(sorted_folders) < count:
                        selected_folders = sorted_folders
                    else:
                        selected_folders = random.sample(sorted_folders, count)
                elif conditional_random:
                    self.log.emit(f"Conditional Random 옵션 선택됨 (Folder Mode, Random Count: {random_count})")
                    selected_folders = []
                    index = 0
                    while index < len(sorted_folders) and len(selected_folders) < count:
                        selected_folders.append(sorted_folders[index])
                        index += (random_count + 1)
                else:
                    selected_folders = sorted_folders[:count]

                total_folders = len(selected_folders)
                self.log.emit(f"Specified Date and Time: {specified_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                self.log.emit(f"Number of Folders to Copy: {total_folders}")

                total_processed_folders = 0
                with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                    futures = []
                    for folder_path in selected_folders:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {total_processed_folders}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {total_processed_folders}")
                            return
                        folder_name = os.path.basename(folder_path)
                        dst_folder = os.path.join(target, folder_name)
                        self.log.emit(f"Source Folder path : {folder_path}")
                        self.log.emit(f"Destination Folder path : {dst_folder}")
                        futures.append(executor.submit(self.copy_folder_filtered, folder_path, dst_folder, formats))
                    for future in as_completed(futures):
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {total_processed_folders}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {total_processed_folders}")
                            return
                        result = future.result()
                        self.log.emit(result)
                        total_processed_folders += 1
                        progress_percent = int((total_processed_folders / total_folders) * 100)
                        self.progress.emit(min(progress_percent, 100))
                self.finished.emit(f"Date-Based Copy (Folder Mode) 완료. 총 처리한 폴더: {total_processed_folders}")
                self.log.emit("------ Date-Based Copy (Folder Mode) 작업 완료 ------")

            elif mode == 'image':
                if not fov_numbers:
                    self.log.emit("Image 모드에서는 FOV Numbers를 입력해야 합니다.")
                    self.finished.emit("Date-Based Copy 중지됨.")
                    return

                # 폴더 선택 (랜덤 옵션 적용)
                if strong_random:
                    self.log.emit("Strong Random 옵션 선택됨 (Image Mode)")
                    if len(sorted_folders) < count:
                        selected_folders = sorted_folders
                    else:
                        selected_folders = random.sample(sorted_folders, count)
                elif conditional_random:
                    self.log.emit(f"Conditional Random 옵션 선택됨 (Image Mode, Random Count: {random_count})")
                    selected_folders = []
                    index = 0
                    # 수정: 각 폴더를 선택할 때, random_count 만큼 건너뛰도록 (기존 random_count+1 대신 random_count 사용)
                    while index < len(sorted_folders) and len(selected_folders) < count:
                        selected_folders.append(sorted_folders[index])
                        index += random_count
                else:
                    selected_folders = sorted_folders[:count]

                total_folders = len(selected_folders)
                self.log.emit(f"총 선택된 폴더 수 (Image Mode): {total_folders}")
                total_processed_folders = 0
                total_processed_images = 0

                # 각 폴더별로 fov number에 해당하는 이미지들을 복사
                for i, folder_path in enumerate(selected_folders, start=1):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {total_processed_folders}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {total_processed_folders}")
                        return
                    inner_id = os.path.basename(folder_path)
                    source_inner_id_folder = folder_path
                    try:
                        with os.scandir(source_inner_id_folder) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                    except Exception as e:
                        self.log.emit(f"이미지 목록 가져오기 중 오류: {source_inner_id_folder} | 에러: {e}")
                        continue

                    matching_images = []
                    for image in image_files:
                        parts = image.split('_', 1)
                        if len(parts) < 2:
                            self.log.emit(f"파일 이름 형식 오류: {image}")
                            continue
                        fov_part = parts[0]
                        if 'fov' in fov_part.lower():
                            fov_part = fov_part.lower().replace('fov', '')
                        fov_number = ''.join(filter(str.isdigit, fov_part))
                        if fov_number in fov_numbers:
                            matching_images.append(image)

                    if not matching_images:
                        self.log.emit(f"폴더 {source_inner_id_folder}에 FOV Number와 매칭되는 이미지가 없습니다.")
                    else:
                        self.log.emit(f"폴더 {source_inner_id_folder}에서 {len(matching_images)}개의 이미지 복사 시작")
                        with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                            futures = []
                            for image in matching_images:
                                src_file = os.path.join(source_inner_id_folder, image)
                                parts = image.split('_', 1)
                                fov_part = parts[0]
                                if 'fov' in fov_part.lower():
                                    fov_part = fov_part.lower().replace('fov', '')
                                fov_number = ''.join(filter(str.isdigit, fov_part))
                                file_base, file_ext = os.path.splitext(image)
                                new_file_name = f"{inner_id}_{fov_number}{file_ext}"
                                dst_file = os.path.join(target, new_file_name)
                                if os.path.exists(dst_file):
                                    self.log.emit(f"파일이 이미 존재하여 건너뜁니다: {dst_file}")
                                    continue
                                futures.append(executor.submit(self.copy_file, src_file, dst_file))
                            for future in as_completed(futures):
                                if self._is_stopped:
                                    self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                                    self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                                    return
                                result = future.result()
                                if result.startswith("오류 발생"):
                                    self.log.emit(result)
                                else:
                                    total_processed_images += 1
                                    self.log.emit(result)
                    total_processed_folders += 1
                    progress_percent = int((total_processed_folders / total_folders) * 100)
                    self.progress.emit(min(progress_percent, 100))
                self.finished.emit(f"Date-Based Copy (Image Mode) 완료. 총 처리한 폴더: {total_processed_folders}, 이미지: {total_processed_images}")
                self.log.emit("------ Date-Based Copy (Image Mode) 작업 완료 ------")
        except Exception as e:
            logging.error("Date-Based Copy 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Date-Based Copy 중 오류 발생.")

    def image_format_copy(self, task):
        self.log.emit("------ Image Format Copy 작업 시작 ------")
        try:
            sources = task['sources']
            targets = task['targets']
            formats = task['formats']

            if not sources or not targets:
                self.log.emit("Source 또는 Target 경로가 설정되지 않았습니다.")
                self.finished.emit("Image Format Copy 중지됨.")
                return

            total_tasks = len(sources)
            total_processed_folders = 0
            total_processed_images = 0

            total_images = 0
            for source, target in zip(sources, targets):
                if os.path.exists(source):
                    try:
                        with os.scandir(source) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                    except Exception as e:
                        self.log.emit(f"이미지 목록 가져오기 중 오류 발생: {source} | 에러: {e}")
                        continue
                    filtered_images = []
                    for img in image_files:
                        if img.lower().endswith('.jpg'):
                            if 'org_jpg' in formats and not img.lower().startswith('fov') and '_fov' not in img.lower():
                                filtered_images.append(img)
                            elif 'fov_jpg' in formats and img.lower().startswith('fov'):
                                filtered_images.append(img)
                        elif img.lower().endswith('.bmp') and '.bmp' in formats:
                            filtered_images.append(img)
                        elif img.lower().endswith('.mim') and '.mim' in formats:
                            filtered_images.append(img)
                        elif img.lower().endswith('.png') and '.png' in formats:
                            filtered_images.append(img)
                    total_images += len(filtered_images)

            if total_images == 0:
                self.log.emit("선택한 이미지 포맷에 해당하는 이미지가 없습니다.")
                self.finished.emit("Image Format Copy 완료.")
                return

            self.log.emit(f"총 복사할 이미지 수: {total_images}")

            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for source, target in zip(sources, targets):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                        return

                    if not os.path.exists(source):
                        self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                        continue
                    if not os.path.exists(target):
                        try:
                            os.makedirs(target)
                            self.log.emit(f"Target 경로 생성: {target}")
                        except Exception as e:
                            self.log.emit(f"Target 경로 생성 실패: {target} | 에러: {e}")
                            continue

                    try:
                        with os.scandir(source) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                    except Exception as e:
                        self.log.emit(f"이미지 목록 가져오기 중 오류 발생: {source} | 에러: {e}")
                        continue
                    filtered_images = []
                    for img in image_files:
                        if img.lower().endswith('.jpg'):
                            if 'org_jpg' in formats and not img.lower().startswith('fov') and '_fov' not in img.lower():
                                filtered_images.append(img)
                            elif 'fov_jpg' in formats and img.lower().startswith('fov'):
                                filtered_images.append(img)
                        elif img.lower().endswith('.bmp') and '.bmp' in formats:
                            filtered_images.append(img)
                        elif img.lower().endswith('.mim') and '.mim' in formats:
                            filtered_images.append(img)
                        elif img.lower().endswith('.png') and '.png' in formats:
                            filtered_images.append(img)

                    for file_name in filtered_images:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                            return
                        src_file = os.path.join(source, file_name)
                        dst_file = os.path.join(target, file_name)
                        futures.append(executor.submit(self.copy_file, src_file, dst_file))

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        total_processed_images += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))

            self.finished.emit(f"Image Format Copy 완료. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
            self.log.emit("------ Image Format Copy 작업 완료 ------")
        except Exception as e:
            logging.error("Image Format Copy 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Image Format Copy 중 오류 발생.")

    def simulation_foldering(self, task):
        self.log.emit("------ Simulation Foldering 작업 시작 ------")
        # 기능 구현 필요
        self.finished.emit("Simulation Foldering 작업 완료.")

    def basic_sorting(self, task):
        self.log.emit("------ Basic Sorting 작업 시작 ------")
        try:
            source = task['source']
            target = task['target']
            inner_id_list_path = task.get('inner_id_list', '')
            use_inner_id = task.get('use_inner_id', False)
            fov_number_input = task.get('fov_number', '').strip()
            inner_id = task.get('inner_id', '').strip()
            formats = task['formats']

            if fov_number_input:
                fov_numbers_raw = [num.strip() for num in fov_number_input.split(',') if num.strip()]
                fov_numbers = []
                invalid_fov = []
                for part in fov_numbers_raw:
                    if '/' in part:
                        try:
                            start, end = part.split('/')
                            start = int(start.strip())
                            end = int(end.strip())
                            if start > end:
                                invalid_fov.append(part)
                            else:
                                fov_numbers.extend([str(n) for n in range(start, end+1)])
                        except Exception as e:
                            invalid_fov.append(part)
                    else:
                        if part.isdigit():
                            fov_numbers.append(part)
                        else:
                            invalid_fov.append(part)
                if invalid_fov:
                    self.log.emit(f"다음 FOV Number가 유효하지 않습니다: {', '.join(invalid_fov)}")
                    self.finished.emit("Basic Sorting 중지됨.")
                    return
            else:
                fov_numbers = []

            inner_ids = []

            if inner_id_list_path and os.path.exists(inner_id_list_path):
                try:
                    with os.scandir(inner_id_list_path) as it:
                        inner_ids = [entry.name for entry in it if entry.is_dir() and entry.name.lower() not in ['ok', 'ng', 'ng_info', 'crop', 'thumbnail']]
                except Exception as e:
                    self.log.emit(f"Inner ID List Path에서 폴더 목록 가져오기 중 오류: {str(e)}")
                    self.finished.emit("Basic Sorting 중지됨.")
                    return
            elif use_inner_id and inner_id:
                inner_ids = [inner_id]
            else:
                self.log.emit("Inner ID List Path도 Inner ID도 설정되지 않았습니다.")
                self.finished.emit("Basic Sorting 중지됨.")
                return

            if not inner_ids:
                self.log.emit("유효한 Inner ID가 없습니다.")
                self.finished.emit("Basic Sorting 완료.")
                return

            if not fov_numbers:
                self.log.emit("FOV Number가 입력되지 않았습니다.")
                self.finished.emit("Basic Sorting 중지됨.")
                return

            if not os.path.exists(source):
                self.log.emit(f"Source Path가 존재하지 않습니다: {source}")
                self.finished.emit("Basic Sorting 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            total_folders = len(inner_ids)
            total_images = 0
            for folder_name in inner_ids:
                source_folder = os.path.join(source, folder_name)
                if os.path.exists(source_folder):
                    try:
                        with os.scandir(source_folder) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                        matching_files = [f for f in image_files
                                        if any(f.split('_', 1)[0] == num for num in fov_numbers)]
                        total_images += len(matching_files)
                    except Exception as e:
                        self.log.emit(f"이미지 목록 가져오기 중 오류: {source_folder} | 에러: {e}")
            if total_images == 0:
                self.log.emit("선택한 FOV Number에 해당하는 이미지가 없습니다.")
                self.finished.emit("Basic Sorting 완료.")
                return

            total_tasks = total_images
            total_processed = 0

            for i, folder_name in enumerate(inner_ids, start=1):
                if self._is_stopped:
                    self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                    self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                    return

                source_folder = os.path.join(source, folder_name)
                if not os.path.exists(source_folder):
                    self.log.emit(f"Source Path 내에 '{folder_name}' 폴더가 존재하지 않습니다.")
                    continue

                try:
                    with os.scandir(source_folder) as it:
                        image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                except Exception as e:
                    self.log.emit(f"이미지 목록 가져오기 중 오류: {source_folder} | 에러: {e}")
                    continue

                if not image_files:
                    self.log.emit(f"'{folder_name}' 폴더에 지정된 이미지 포맷의 파일이 없습니다.")
                    continue

                matching_files = []
                for file in image_files:
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                        return
                    parts = file.split('_', 1)
                    if len(parts) < 2:
                        self.log.emit(f"파일 이름 형식 오류: {file}")
                        continue
                    file_fov_number = parts[0].lower().replace('fov', '') if 'fov' in parts[0].lower() else parts[0]

                    if file_fov_number in fov_numbers:
                        if file.lower().endswith('.jpg'):
                            if 'org_jpg' in formats and not file.lower().startswith('fov') and '_fov' not in file.lower():
                                matching_files.append(file)
                            if 'fov_jpg' in formats and file.lower().startswith('fov'):
                                matching_files.append(file)
                        else:
                            matching_files.append(file)

                if not matching_files:
                    self.log.emit(f"'{folder_name}' 폴더에 FOV Number '{', '.join(fov_numbers)}'에 매칭되는 파일이 없습니다.")
                    continue

                with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                    futures = []
                    for image_file in matching_files:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                            return
                        src_file = os.path.join(source_folder, image_file)
                        file_base, file_ext = os.path.splitext(image_file)
                        new_file_name = f"{folder_name}_{file_base}{file_ext}"
                        dst_file = os.path.join(target, new_file_name)
                        futures.append(executor.submit(self.copy_file, src_file, dst_file))
                    
                    for future in as_completed(futures):
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                            return
                        result = future.result()
                        if result.startswith("오류 발생"):
                            self.log.emit(result)
                        else:
                            total_processed += 1
                            self.log.emit(result)
                            progress_percent = int((total_processed / total_tasks) * 100)
                            self.progress.emit(min(progress_percent, 100))
                self.log.emit(f"'{folder_name}' 폴더에서 {len(matching_files)}개의 파일을 복사했습니다.")
                progress_percent = int((total_processed / total_tasks) * 100)
                self.progress.emit(min(progress_percent, 100))
            self.finished.emit(f"Basic Sorting 완료. 총 처리한 폴더: {total_folders}, 이미지: {total_processed}")
            self.log.emit("------ Basic Sorting 작업 완료 ------")
        except Exception as e:
            logging.error("Basic Sorting 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    # -------------------------------
    # Crop 작업
    def crop_images(self, task):
        self.log.emit("------ Crop 작업 시작 ------")
        try:
            source = task['source']
            target = task['target']
            formats = task['formats']
            crop_area = task['crop_area']

            if not os.path.exists(source):
                self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                self.finished.emit("Crop 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            try:
                crop_coords = tuple(map(int, crop_area.split(',')))
                if len(crop_coords) != 4:
                    raise ValueError("Crop area must have four integers separated by commas.")
            except Exception as e:
                self.log.emit(f"Crop Area 형식 오류: {str(e)}")
                self.finished.emit("Crop 중지됨.")
                return

            try:
                with os.scandir(source) as it:
                    image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
            except Exception as e:
                self.log.emit(f"이미지 목록 가져오기 중 오류: {source} | 에러: {e}")
                self.finished.emit("Crop 중지됨.")
                return

            total_images = len(image_files)
            if total_images == 0:
                self.log.emit("선택한 이미지 포맷에 해당하는 이미지가 없습니다.")
                self.finished.emit("Crop 완료.")
                return
            total_processed_images = 0

            self.log.emit(f"Cropping Area: {crop_coords}")

            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for file_name in image_files:
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    src_file = os.path.join(source, file_name)
                    dst_file = os.path.join(target, file_name)
                    futures.append(executor.submit(self.crop_image, src_file, dst_file, crop_coords))

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result:
                        total_processed_images += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))
            self.finished.emit(f"Crop 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ Crop 작업 완료 ------")
        except Exception as e:
            logging.error("Crop 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Crop 중 오류 발생.")

    # ---------------------------------------------------------
    # 7) NG Count
    def ng_count(self, task):
        self.log.emit("------ NG Count 작업 시작 ------")
        try:
            ng_folder = task['ng_folder']
            if not os.path.exists(ng_folder):
                self.log.emit(f"NG 폴더가 존재하지 않습니다: {ng_folder}")
                self.finished.emit("NG Count 중지됨.")
                return

            try:
                with os.scandir(ng_folder) as it:
                    cam_folders = [entry.name for entry in it if entry.is_dir() and entry.name.startswith('Cam_')]
            except Exception as e:
                self.log.emit(f"Cam_ 폴더 탐색 중 오류 발생: {str(e)}")
                self.finished.emit("NG Count 중지됨.")
                return

            total_cams = len(cam_folders)
            total_defects = 0
            ng_count_data = []

            if total_cams == 0:
                self.log.emit("NG 폴더 내에 'Cam_'으로 시작하는 폴더가 없습니다.")
                self.finished.emit("NG Count 완료.")
                return

            for i, cam in enumerate(cam_folders, start=1):
                if self._is_stopped:
                    self.log.emit(f"작업이 중지되었습니다. 총 Cam: {total_cams}, 총 Defect: {total_defects}")
                    self.finished.emit(f"작업 중지됨. 총 Cam: {total_cams}, 총 Defect: {total_defects}")
                    return

                cam_path = os.path.join(ng_folder, cam)
                try:
                    with os.scandir(cam_path) as it:
                        defect_folders = [entry.name for entry in it if entry.is_dir()]
                except Exception as e:
                    self.log.emit(f"Defect 폴더 탐색 중 오류 발생: {cam_path} | 에러: {e}")
                    continue

                for defect in defect_folders:
                    defect_path = os.path.join(cam_path, defect)
                    try:
                        with os.scandir(defect_path) as it_defect:
                            count = sum(1 for _ in it_defect if _.is_dir())
                        ng_count_data.append([cam, defect, count])
                        total_defects += count
                    except Exception as e:
                        self.log.emit(f"Defect 폴더 내 항목 수 계산 중 오류 발생: {defect_path} | 에러: {e}")

                progress_percent = int((i / total_cams) * 100)
                self.progress.emit(min(progress_percent, 100))

            self.ng_count_result.emit(ng_count_data)
            self.finished.emit(f"NG Count 완료. 총 Cam: {total_cams}, 총 Defect: {total_defects}")
            self.log.emit("------ NG Count 작업 완료 ------")
        except Exception as e:
            logging.error("NG Count 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("NG Count 중 오류 발생.")

    # ---------------------------------------------------------
    # --------------------- 새로 추가된 기능들 -----------------
    # ---------------------------------------------------------
    # A) ATTACH FOV
    def attach_fov(self, task):
        """
        search folder path #1, #2 하위(재귀)에서 fov*.jpg 수집.
        끝에서 15자리 폴더명이 일치하면 같은 시료라 판단.
        동일 fov num이면 좌우로 이미지 붙임 + 주석(좌상단에 파일 경로, fov number).
        """
        self.log.emit("------ Attach FOV 작업 시작 ------")

        try:
            search1 = task.get('search1', '')
            search2 = task.get('search2', '')
            target = task.get('target', '')
            fov_number_input = task.get('fov_number', '').strip()

            if not os.path.isdir(search1) or not os.path.isdir(search2):
                self.log.emit("Search Folder Path가 유효하지 않습니다.")
                self.finished.emit("Attach FOV 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            # fov_number 파싱
            if fov_number_input:
                fov_numbers_raw = [num.strip() for num in fov_number_input.split(',') if num.strip()]
                fov_numbers = []
                for part in fov_numbers_raw:
                    if '/' in part:
                        try:
                            start, end = part.split('/')
                            start = int(start.strip())
                            end = int(end.strip())
                            if start <= end:
                                fov_numbers.extend([str(n) for n in range(start, end+1)])
                        except:
                            pass
                    else:
                        if part.isdigit():
                            fov_numbers.append(part)
            else:
                # fov_number 입력이 아예 없으면 None 처리
                fov_numbers = None

            # 검색 (재귀적으로 fov*.jpg 찾기)
            dict1 = self.recursive_find_fov_images(search1)
            dict2 = self.recursive_find_fov_images(search2)

            # dict 구조:
            # dict1[(last15, fovX)] = [ (이미지파일경로), ... ] (리스트 가능)
            # dict2[(last15, fovX)] = [ (이미지파일경로), ... ]

            # 교집합 key 추출
            intersection_keys = set(dict1.keys()).intersection(set(dict2.keys()))

            # (fov_numbers가 주어졌다면 필터링)
            if fov_numbers is not None:
                intersection_keys = {
                    k for k in intersection_keys
                    if k[1] in fov_numbers
                }

            if not intersection_keys:
                self.log.emit("교집합 fov 이미지가 없습니다.")
                self.finished.emit("Attach FOV 완료.")
                return

            # 총 작업 건수 계산
            total_jobs = 0
            for k in intersection_keys:
                total_jobs += min(len(dict1[k]), len(dict2[k]))  # 두 쪽 다 존재하는 pair 수만큼

            self.log.emit(f"총 attach할 건수: {total_jobs}")

            total_processed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for key in intersection_keys:
                    # key = (last15, fovNum)
                    images_list_1 = dict1[key]
                    images_list_2 = dict2[key]
                    # 실제로는 1:1 대응일 가능성이 높으나, 혹시 여러 개 있을 수 있음
                    pair_count = min(len(images_list_1), len(images_list_2))
                    for i in range(pair_count):
                        src_file_1 = images_list_1[i]
                        src_file_2 = images_list_2[i]
                        # 작업 등록
                        futures.append(
                            executor.submit(self.attach_two_images, src_file_1, src_file_2, key, target)
                        )

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리 수: {total_processed}")
                        self.finished.emit(f"Attach FOV 작업 중지됨. 총 처리 수: {total_processed}")
                        return
                    result = future.result()
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        total_processed += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed / total_jobs) * 100)
                        self.progress.emit(min(progress_percent, 100))

            self.finished.emit(f"Attach FOV 완료. 총 처리한 이미지 쌍: {total_processed}")
            self.log.emit("------ Attach FOV 작업 완료 ------")

        except Exception as e:
            logging.error("Attach FOV 작업 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Attach FOV 중 오류 발생.")

    def recursive_find_fov_images(self, root_folder):
        """
        root_folder 하위 모든 폴더를 재귀로 돌며 fov*.jpg 파일을 찾는다.
        (끝에서 15자리 폴더명을 key, fov번호를 subkey로 해서 dict에 저장)
        반환: dict[(last15, fovNum)] = [img_path1, img_path2, ...]
        """
        ignore_list = {'ok', 'ng', 'ng_info', 'crop', 'thumbnail'}
        result_dict = {}
        for dirpath, dirnames, filenames in os.walk(root_folder):
            # 1) 하위 폴더 목록(dirnames)에서 ignore_list에 해당하는 폴더는 제거(재귀 탐색 방지)
            dirnames[:] = [d for d in dirnames if d.lower() not in ignore_list]

            # 2) 현재 폴더 자체가 ignore_list에 해당하면, 파일 수집 스킵
            folder_name = os.path.basename(dirpath)
            if folder_name.lower() in ignore_list:
                continue

            # 이후 fov*.jpg 수집 로직
            last15 = folder_name[-15:] if len(folder_name) >= 15 else folder_name
            for filename in filenames:
                if filename.lower().startswith('fov') and filename.lower().endswith('.jpg'):
                    fovnum = ''.join(filter(str.isdigit, filename.lower().replace('fov', '')))
                    if not fovnum:
                        # 숫자 추출 실패 시 건너뜀
                        continue
                    key = (last15, fovnum)
                    full_path = os.path.join(dirpath, filename)
                    if key not in result_dict:
                        result_dict[key] = []
                    result_dict[key].append(full_path)

        return result_dict

    def attach_two_images(self, src1, src2, key, target):
        """
        두 이미지를 좌우로 붙이고,
        좌상단에 주석(파일경로, fov)을 찍은 뒤 target 폴더에 저장.
        """
        try:
            last15, fovnum = key
            im1 = Image.open(src1)
            im2 = Image.open(src2)
            width = im1.width + im2.width
            height = max(im1.height, im2.height)
            new_img = Image.new('RGB', (width, height), (255, 255, 255))
            new_img.paste(im1, (0, 0))
            new_img.paste(im2, (im1.width, 0))

            draw = ImageDraw.Draw(new_img)

            # 폰트가 필요하다면, OS 상의 폰트 경로를 직접 지정해야 합니다.
            # 여기서는 기본 PIL 폰트 사용 예시
            # (원하시면 ImageFont.truetype("arial.ttf", 20) 처럼 수정 가능)
            font = ImageFont.load_default()

            # 왼쪽 이미지 상단 주석
            draw.text((10, 10), f"{os.path.basename(src1)}\nfov:{fovnum}", fill=(0, 0, 0), font=font)

            # 오른쪽 이미지 상단 주석 (오른쪽 이미지는 x좌표를 im1.width 기준으로 조금 오른쪽에)
            draw.text((im1.width + 10, 10), f"{os.path.basename(src2)}\nfov:{fovnum}", fill=(0, 0, 0), font=font)

            # 저장 파일명
            out_filename = f"attached_{last15}_{fovnum}.jpg"
            dst_file = os.path.join(target, out_filename)

            new_img.save(dst_file)
            return f"Attached: {src1} + {src2} => {dst_file}"
        except Exception as e:
            logging.error("attach_two_images 중 오류 발생", exc_info=True)
            return f"오류 발생: {str(e)}"

    # B) MIM to BMP (Placeholder)
    def mim_to_bmp(self, task):
        self.log.emit("------ MIM to BMP 작업 시작 ------")
        # 여기서 MIM -> BMP 변환 로직을 추가 구현할 수 있습니다.
        # 현재는 예시 placeholder만 제공
        self.log.emit("아직 구현되지 않은 Placeholder 기능입니다.")
        self.finished.emit("MIM to BMP 작업 완료(Placeholder).")

    # C) TEMP (아무 기능 X)
    def temp_operation(self, task):
        self.log.emit("------ TEMP 작업(미정) 시작 ------")
        # 실제 동작 없음
        self.log.emit("TEMP 기능은 현재 미정 상태라 동작하지 않습니다.")
        self.finished.emit("TEMP 작업 완료 (실제 동작 없음).")

    # ---------------------------------------------------------
    # --------------------- 유틸 함수들 ------------------------
    # ---------------------------------------------------------
    def is_valid_file(self, filename, formats):
        if not formats:
            return False
        for fmt in formats:
            if fmt.lower() == 'org_jpg':
                if filename.lower().endswith('.jpg') and not filename.lower().startswith('fov') and '_fov' not in filename.lower():
                    return True
            elif fmt.lower() == 'fov_jpg':
                if filename.lower().endswith('.jpg') and filename.lower().startswith('fov'):
                    return True
            else:
                if filename.lower().endswith(fmt.lower()):
                    return True
        return False

    def crop_image(self, src, dst, crop_coords):
        try:
            with Image.open(src) as img:
                cropped_img = img.crop(crop_coords)
                cropped_img.save(dst)
            return f"Cropped {src} to {dst}"
        except Exception as e:
            logging.error("이미지 크롭 중 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    def copy_file(self, src, dst):
        try:
            shutil.copy2(src, dst)
            return f"Copied {src} to {dst}"
        except Exception as e:
            logging.error("파일 복사 중 오류", exc_info=True)
            if os.path.exists(dst):
                os.remove(dst)
            return f"오류 발생: {str(e)}"

    def copy_folder(self, src, dst):
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True)
            return f"Copied folder {src} to {dst}"
        except Exception as e:
            logging.error("폴더 복사 중 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    def copy_folder_filtered(self, src, dst, formats):
        try:
            if not os.path.exists(dst):
                os.makedirs(dst)
            count = 0
            with os.scandir(src) as it:
                for entry in it:
                    if entry.is_file() and self.is_valid_file(entry.name, formats):
                        src_file = os.path.join(src, entry.name)
                        dst_file = os.path.join(dst, entry.name)
                        result = self.copy_file(src_file, dst_file)
                        if not result.startswith("오류 발생"):
                            count += 1
            return f"Copied {count} file(s) from {src} to {dst} (filtered)"
        except Exception as e:
            logging.error("Filtered folder copy 중 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    # --- 수정된 collect_inner_ids 함수 ---
    # sources가 리스트인 경우 각 경로의 basename(Inner ID)만 추출
    def collect_inner_ids(self, sources):
        inner_ids = set()
        if isinstance(sources, list):
            for source in sources:
                if not os.path.exists(source):
                    self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                    continue
                inner_id = os.path.basename(source.rstrip(os.sep))
                if inner_id.lower() in ['ok', 'ng', 'ng_info', 'crop', 'thumbnail']:
                    continue
                inner_ids.add(inner_id)
        else:
            if not os.path.exists(sources):
                self.log.emit(f"Source 경로가 존재하지 않습니다: {sources}")
            else:
                inner_id = os.path.basename(sources.rstrip(os.sep))
                if inner_id.lower() not in ['ok', 'ng', 'ng_info', 'crop', 'thumbnail']:
                    inner_ids.add(inner_id)
        return inner_ids


    def collect_inner_ids_from_source2(self, source2):
        inner_ids = set()
        if not os.path.exists(source2):
            self.log.emit(f"Source2 경로가 존재하지 않습니다: {source2}")
            return inner_ids
        try:
            with os.scandir(source2) as it:
                inner_ids = {entry.name for entry in it if entry.is_dir() and entry.name.lower() not in ['ok', 'ng', 'ng_info', 'crop', 'thumbnail']}
        except Exception as e:
            self.log.emit(f"Source2에서 Inner ID 수집 중 오류: {str(e)}")
        return inner_ids

    def collect_images_to_copy(self, inner_ids, source, formats):
        images_to_copy = {}
        total_images = 0
        for inner_id in inner_ids:
            source_inner_id_folder = os.path.join(source, inner_id)
            if not os.path.exists(source_inner_id_folder):
                self.log.emit(f"Source 경로에 Inner ID 폴더가 존재하지 않습니다: {source_inner_id_folder}")
                continue
            try:
                with os.scandir(source_inner_id_folder) as it:
                    images = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                if images:
                    images_to_copy[inner_id] = images
                    total_images += len(images)
            except Exception as e:
                self.log.emit(f"이미지 수집 중 오류 발생: {source_inner_id_folder} | 에러: {e}")
        return images_to_copy, total_images
