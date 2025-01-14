import sys
import os
import shutil
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QProgressBar, QMessageBox, QLabel, QHBoxLayout, QTextEdit,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout, QDateTimeEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDateTime
from PyQt5.QtGui import QIcon
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 로그 설정
logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')


class WorkerThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    ng_count_result = pyqtSignal(list)  # NG Count 결과를 전달하는 시그널
    finished = pyqtSignal(str)

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._is_stopped = False

    def run(self):
        try:
            operation = self.task['operation']
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
            elif operation == 'resize':
                self.resize_images(self.task)
            elif operation == 'flip':
                self.flip_images(self.task)
            elif operation == 'rotate':
                self.rotate_images(self.task)
            else:
                self.log.emit(f"알 수 없는 작업 유형: {operation}")
                self.finished.emit("알 수 없는 작업 유형.")
        except Exception as e:
            logging.error("작업 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중 오류 발생.")

    def stop(self):
        self._is_stopped = True
    def collect_inner_ids(self, sources1):
        """
        sources1 내의 모든 서브폴더를 수집하여 inner_ids 집합을 반환.
        """
        inner_ids = set()
        for source1_path in sources1:
            if not os.path.exists(source1_path):
                self.log.emit(f"Source Path #1이 존재하지 않습니다: {source1_path}")
                continue
            try:
                subfolders = [
                    f for f in os.listdir(source1_path)
                    if os.path.isdir(os.path.join(source1_path, f)) and f.lower() not in ['ok', 'ng']
                ]
                inner_ids.update(subfolders)
                self.log.emit(f"추가된 서브폴더들 from {source1_path}: {subfolders}")
            except Exception as e:
                self.log.emit(f"서브폴더 수집 중 오류 발생: {source1_path} | 에러: {e}")
        return inner_ids

    def collect_inner_ids_from_source2(self, source2):
        """
        source2 내의 모든 서브폴더를 수집하여 inner_ids_source2 집합을 반환.
        """
        inner_ids_source2 = set()
        if not os.path.exists(source2):
            self.log.emit(f"source2 경로가 존재하지 않습니다: {source2}")
            return inner_ids_source2
        try:
            inner_ids_source2 = {f for f in os.listdir(source2) 
                                 if os.path.isdir(os.path.join(source2, f)) and f.lower() not in ['ok', 'ng']}
            self.log.emit(f"source2에서 수집한 Inner IDs: {inner_ids_source2}")
        except Exception as e:
            self.log.emit(f"source2에서 Inner ID 수집 중 오류 발생: {str(e)}")
        return inner_ids_source2

    def create_target_folders(self, target, inner_ids):
        """
        타겟 디렉토리에 inner_id 기반 폴더를 생성.
        """
        for inner_id in inner_ids:
            target_inner_id_folder = os.path.join(target, inner_id)
            try:
                if not os.path.exists(target_inner_id_folder):
                    os.makedirs(target_inner_id_folder)
                    self.log.emit(f"Created target Inner ID folder: {target_inner_id_folder}")
                else:
                    self.log.emit(f"Target Inner ID folder already exists: {target_inner_id_folder}")
            except Exception as e:
                self.log.emit(f"타겟 폴더 생성 중 오류 발생: {target_inner_id_folder} | 에러: {e}")

    def collect_images_to_copy(self, inner_ids, source2, formats):
        """
        복사할 이미지 파일들을 inner_id별로 수집.
        """
        images_to_copy = {}
        total_images = 0
        for inner_id in inner_ids:
            source_inner_id_folder = os.path.join(source2, inner_id)
            if not os.path.exists(source_inner_id_folder):
                self.log.emit(f"source2 경로에 Inner ID 폴더가 존재하지 않습니다: {source_inner_id_folder}")
                continue
            try:
                images = [
                    f for f in os.listdir(source_inner_id_folder)
                    if os.path.isfile(os.path.join(source_inner_id_folder, f)) and
                    any(f.lower().endswith(fmt.lower()) for fmt in formats)
                ]
                if images:
                    images_to_copy[inner_id] = images
                    total_images += len(images)
                    self.log.emit(f"{inner_id} 폴더의 이미지 수: {len(images)}")
            except Exception as e:
                self.log.emit(f"이미지 수집 중 오류 발생: {source_inner_id_folder} | 에러: {e}")
        return images_to_copy, total_images

    # 각 기능별 메서드 구현
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

            # Target 디렉토리 존재 여부 확인 및 생성
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

            # Inner ID 폴더 목록 가져오기 (sources1 내의 모든 서브폴더)
            inner_ids_sources1 = self.collect_inner_ids(sources1)
            inner_ids_source2 = self.collect_inner_ids_from_source2(source2)
            matched_inner_ids = inner_ids_sources1.intersection(inner_ids_source2)

            total_matched_inner_ids = len(matched_inner_ids)
            if total_matched_inner_ids == 0:
                self.log.emit("sources1과 source2 모두에 존재하는 Inner ID가 없습니다.")
                self.finished.emit("NG Folder Sorting 완료.")
                return
            self.log.emit(f"총 매칭된 Inner ID 수: {total_matched_inner_ids}")

            # 타겟 경로에 매칭된 Inner ID 기반 폴더 생성
            self.create_target_folders(target, matched_inner_ids)

            # 전체 이미지 수 계산 및 이미지 수집
            images_to_copy, total_images = self.collect_images_to_copy(matched_inner_ids, source2, formats)

            if total_images == 0:
                self.log.emit("선택한 이미지 포맷에 해당하는 이미지가 없습니다.")
                self.finished.emit("NG Folder Sorting 완료.")
                return
            self.log.emit(f"총 복사할 이미지 수: {total_images}")

            total_processed_images = 0

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {}
                for inner_id, images in images_to_copy.items():
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return

                    source_inner_id_folder = os.path.join(source2, inner_id)
                    target_inner_id_folder = os.path.join(target, inner_id)

                    for image in images:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                            return

                        src_file = os.path.join(source_inner_id_folder, image)
                        dst_file = os.path.join(target_inner_id_folder, image)

                        # 파일이 이미 존재하는지 확인 (옵션: 덮어쓸지 여부)
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
                        # 전체 진행률 업데이트
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

            self.finished.emit(f"NG Folder Sorting 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ NG Folder Sorting 작업 완료 ------")
        except Exception as e:
            logging.error("NG Folder Sorting 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("NG Folder Sorting 중 오류 발생.")

        def date_based_copy(self, task):
            self.log.emit("------ Date-Based Copy 작업 시작 ------")
            try:
                source = task['source']
                target = task['target']
                specified_datetime = datetime(task['year'], task['month'], task['day'],
                                             task['hour'], task['minute'], task['second'])
                count = task['count']

                if not os.path.exists(source):
                    self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                    self.finished.emit("Date-Based Copy 중지됨.")
                    return
                if not os.path.exists(target):
                    os.makedirs(target)

                # 전체 폴더 수 미리 계산
                all_folders = [f for f in os.listdir(source)
                               if os.path.isdir(os.path.join(source, f))]
                # 폴더의 수정 날짜 필터링
                matching_folders = []
                for folder in all_folders:
                    folder_path = os.path.join(source, folder)
                    try:
                        folder_mtime = datetime.fromtimestamp(os.path.getmtime(folder_path))
                        if folder_mtime >= specified_datetime:
                            matching_folders.append(folder_path)
                            if len(matching_folders) >= count:
                                break
                    except Exception as e:
                        logging.error(f"폴더 수정 시간 가져오기 중 오류: {folder_path}", exc_info=True)
                        self.log.emit(f"폴더 수정 시간 가져오기 중 오류: {folder_path} - {str(e)}")

                total_folders = len(matching_folders)
                if total_folders == 0:
                    self.log.emit("지정된 날짜 이후의 복사할 폴더가 없습니다.")
                    self.finished.emit("Date-Based Copy 완료.")
                    return

                total_processed_folders = 0

                self.log.emit(f"Specified Date and Time: {specified_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                self.log.emit(f"Number of Folders to Copy: {total_folders}")

                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = []
                    for folder_path in matching_folders:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {total_processed_folders}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {total_processed_folders}")
                            return
                        folder_name = os.path.basename(folder_path)
                        dst_folder = os.path.join(target, folder_name)

                        self.log.emit(f"Source Folder path : {folder_path}")
                        self.log.emit(f"Destination Folder path : {dst_folder}")

                        futures.append(executor.submit(self.copy_folder, folder_path, dst_folder))

                    for future in as_completed(futures):
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {total_processed_folders}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {total_processed_folders}")
                            return
                        result = future.result()
                        if result.startswith("오류 발생"):
                            self.log.emit(result)
                        else:
                            total_processed_folders += 1
                            self.log.emit(result)
                            # 전체 진행률을 업데이트하기 위해 계산
                            progress_percent = int((total_processed_folders / total_folders) * 100)
                            self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

                self.finished.emit(f"Date-Based Copy 완료. 총 처리한 폴더: {total_processed_folders}")
                self.log.emit("------ Date-Based Copy 작업 완료 ------")
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

            # 전체 이미지 수 미리 계산
            total_images = 0
            for source, target in zip(sources, targets):
                if os.path.exists(source):
                    image_files = [f for f in os.listdir(source)
                                   if any(f.lower().endswith(fmt.lower()) for fmt in formats)]
                    total_images += len(image_files)

            if total_images == 0:
                self.log.emit("선택한 이미지 포맷에 해당하는 이미지가 없습니다.")
                self.finished.emit("Image Format Copy 완료.")
                return

            for i, (source, target) in enumerate(zip(sources, targets), start=1):
                if self._is_stopped:
                    self.log.emit(f"작업이 중지되었습니다. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                    self.finished.emit(f"작업 중지됨. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                    return

                if not os.path.exists(source):
                    self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                    continue
                if not os.path.exists(target):
                    os.makedirs(target)

                # 파일 복사
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = []
                    for file_name in os.listdir(source):
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
                            return
                        if any(file_name.lower().endswith(fmt.lower()) for fmt in formats):
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
                            # 전체 진행률을 업데이트하기 위해 계산
                            progress_percent = int((total_processed_images / total_images) * 100)
                            self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

                self.log.emit(f"Source '{source}'에서 Target '{target}'로 파일을 복사했습니다.")
                total_processed_folders += 1
                progress_percent = int((total_processed_folders / total_tasks) * 100)
                self.progress.emit(min(progress_percent, 100))

            self.finished.emit(f"Image Format Copy 완료. 총 처리한 경로: {total_processed_folders}, 이미지: {total_processed_images}")
            self.log.emit("------ Image Format Copy 작업 완료 ------")
        except Exception as e:
            logging.error("Image Format Copy 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Image Format Copy 중 오류 발생.")
        pass

    def simulation_foldering_worker(self, task):
        # Placeholder for the simulation_foldering implementation
        pass

    def basic_sorting_worker(self, task):
        # Placeholder for the basic_sorting implementation
        pass

    def crop_images_worker(self, task):
        # Placeholder for the crop_images implementation
        pass

    def resize_images_worker(self, task):
        # Placeholder for the resize_images implementation
        pass

    def flip_images_worker(self, task):
        # Placeholder for the flip_images implementation
        pass

    def rotate_images_worker(self, task):
        # Placeholder for the rotate_images implementation
        pass

    def ng_count(self, task):
        self.log.emit("------ NG Count 작업 시작 ------")
        try:
            ng_folder = task['ng_folder']
            if not os.path.exists(ng_folder):
                self.log.emit(f"NG 폴더가 존재하지 않습니다: {ng_folder}")
                self.finished.emit("NG Count 중지됨.")
                return

            # 'Cam_'으로 시작하는 폴더들 탐색
            cam_folders = [f for f in os.listdir(ng_folder) 
                           if os.path.isdir(os.path.join(ng_folder, f)) and f.startswith('Cam_')]
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
                # Defect Name별 폴더 수 카운팅
                defect_folders = [f for f in os.listdir(cam_path) if os.path.isdir(os.path.join(cam_path, f))]
                for defect in defect_folders:
                    defect_path = os.path.join(cam_path, defect)
                    count = len([f for f in os.listdir(defect_path) if os.path.isdir(os.path.join(defect_path, f))])
                    ng_count_data.append([cam, defect, count])
                    total_defects += count

                # 진행률 업데이트 (Cam 단위)
                progress_percent = int((i / total_cams) * 100)
                self.progress.emit(min(progress_percent, 100))

            # NG Count 결과를 표 형식으로 전달
            self.ng_count_result.emit(ng_count_data)

            self.finished.emit(f"NG Count 완료. 총 Cam: {total_cams}, 총 Defect: {total_defects}")
            self.log.emit("------ NG Count 작업 완료 ------")
        except Exception as e:
            logging.error("NG Count 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("NG Count 중 오류 발생.")

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

            # FOV Number를 다중 입력으로 처리 및 유효성 검증
            if fov_number_input:
                # 콤마로 분리하고, 공백 제거
                fov_numbers_raw = [num.strip() for num in fov_number_input.split(',') if num.strip()]
                fov_numbers = []
                invalid_fov = []
                for num in fov_numbers_raw:
                    if num.isdigit():
                        fov_numbers.append(num)
                    else:
                        invalid_fov.append(num)
                if invalid_fov:
                    self.log.emit(f"다음 FOV Number가 유효하지 않습니다: {', '.join(invalid_fov)}")
                    self.finished.emit("Basic Sorting 중지됨.")
                    return
            else:
                fov_numbers = []

            inner_ids = []

            if inner_id_list_path and os.path.exists(inner_id_list_path):
                # Inner ID List Path가 설정된 경우
                inner_ids = [f for f in os.listdir(inner_id_list_path) 
                            if os.path.isdir(os.path.join(inner_id_list_path, f)) and f not in ['OK', 'NG']]
            elif use_inner_id and inner_id:
                # Inner ID가 설정된 경우
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

            total_folders = len(inner_ids)
            total_images = 0
            # 전체 이미지 수 미리 계산
            for folder_name in inner_ids:
                source_folder = os.path.join(source, folder_name)
                if os.path.exists(source_folder):
                    image_files = [f for f in os.listdir(source_folder)
                                   if os.path.isfile(os.path.join(source_folder, f)) and
                                   any(f.lower().endswith(fmt.lower()) for fmt in formats)]
                    matching_files = [f for f in image_files
                                      if any(f.split('_', 1)[0] == num for num in fov_numbers)]
                    total_images += len(matching_files)

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

                # 선택된 이미지 포맷에 맞는 이미지 파일들 가져오기
                image_files = [f for f in os.listdir(source_folder)
                               if os.path.isfile(os.path.join(source_folder, f)) and
                               any(f.lower().endswith(fmt.lower()) for fmt in formats)]

                if not image_files:
                    self.log.emit(f"'{folder_name}' 폴더에 지정된 이미지 포맷의 파일이 없습니다.")
                    continue

                # FOV Numbers에 매칭되는 파일 필터링
                matching_files = []
                for file in image_files:
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                        return
                    parts = file.split('_', 1)  # 첫 번째 언더스코어 기준으로 분리
                    if len(parts) < 2:
                        self.log.emit(f"파일 이름 형식 오류: {file}")
                        continue
                    file_fov_number = parts[0]
                    if file_fov_number in fov_numbers:
                        matching_files.append(file)

                if not matching_files:
                    self.log.emit(f"'{folder_name}' 폴더에 FOV Number '{', '.join(fov_numbers)}'에 매칭되는 파일이 없습니다.")
                    continue

                # 병렬 복사를 위한 ThreadPoolExecutor 사용
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = []
                    for image_file in matching_files:
                        if self._is_stopped:
                            self.log.emit(f"작업이 중지되었습니다. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                            self.finished.emit(f"작업 중지됨. 총 처리한 폴더: {i-1}, 이미지: {total_processed}")
                            return
                        src_file = os.path.join(source_folder, image_file)
                        # 새로운 파일명: (Inner ID)_(원본 이미지 파일명).format
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
                            # 전체 진행률을 업데이트하기 위해 계산
                            progress_percent = int((total_processed / total_tasks) * 100)
                            self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

                self.log.emit(f"'{folder_name}' 폴더에서 {len(matching_files)}개의 파일을 복사했습니다.")
                progress_percent = int((total_processed / total_tasks) * 100)
                self.progress.emit(min(progress_percent, 100))
            self.finished.emit(f"Basic Sorting 완료. 총 처리한 폴더: {total_folders}, 이미지: {total_processed}")
            self.log.emit("------ Basic Sorting 작업 완료 ------")
        except Exception as e:
            logging.error("Basic Sorting 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def crop_images(self, task):
        self.log.emit("------ Crop 작업 시작 ------")
        try:
            # Crop 관련 작업 구현
            # 이 예제에서는 단순히 파일을 복사하는 것으로 가정
            source = task['source']
            target = task['target']
            formats = task['formats']
            crop_area = task['crop_area']  # "left, upper, right, lower" 형식의 문자열

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

            # 전체 이미지 수 미리 계산
            image_files = [f for f in os.listdir(source)
                           if os.path.isfile(os.path.join(source, f)) and
                           any(f.lower().endswith(fmt.lower()) for fmt in formats)]
            total_images = len(image_files)
            total_processed_images = 0

            self.log.emit(f"Cropping Area: {crop_coords}")

            with ThreadPoolExecutor(max_workers=8) as executor:
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
                        # 전체 진행률을 업데이트하기 위해 계산
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

            self.finished.emit(f"Crop 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ Crop 작업 완료 ------")
        except Exception as e:
            logging.error("Crop 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Crop 중 오류 발생.")

    def resize_images(self, task):
        self.log.emit("------ Resize 작업 시작 ------")
        try:
            # Resize 관련 작업 구현
            # 이 예제에서는 단순히 파일을 복사하는 것으로 가정
            source = task['source']
            target = task['target']
            formats = task['formats']
            resize_dimensions = task['resize_dimensions']  # "widthxheight" 형식의 문자열

            if not os.path.exists(source):
                self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                self.finished.emit("Resize 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            try:
                width, height = map(int, resize_dimensions.lower().split('x'))
            except Exception as e:
                self.log.emit(f"Resize Dimensions 형식 오류: {str(e)}")
                self.finished.emit("Resize 중지됨.")
                return

            # 전체 이미지 수 미리 계산
            image_files = [f for f in os.listdir(source)
                           if os.path.isfile(os.path.join(source, f)) and
                           any(f.lower().endswith(fmt.lower()) for fmt in formats)]
            total_images = len(image_files)
            total_processed_images = 0

            self.log.emit(f"Resize Dimensions: {width}x{height}")

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for file_name in image_files:
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    src_file = os.path.join(source, file_name)
                    dst_file = os.path.join(target, file_name)
                    futures.append(executor.submit(self.resize_image, src_file, dst_file, width, height))

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result:
                        total_processed_images += 1
                        self.log.emit(result)
                        # 전체 진행률을 업데이트하기 위해 계산
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

            self.finished.emit(f"Resize 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ Resize 작업 완료 ------")
        except Exception as e:
            logging.error("Resize 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Resize 중 오류 발생.")

    def flip_images(self, task):
        self.log.emit("------ Flip 작업 시작 ------")
        try:
            # Flip 관련 작업 구현
            # 이 예제에서는 단순히 파일을 복사하는 것으로 가정
            source = task['source']
            target = task['target']
            formats = task['formats']
            flip_direction = task['flip_direction']  # "horizontal" 또는 "vertical"

            if not os.path.exists(source):
                self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                self.finished.emit("Flip 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            # Flip Direction 유효성 검증
            if flip_direction.lower() not in ['horizontal', 'vertical']:
                self.log.emit(f"잘못된 Flip Direction: {flip_direction}")
                self.finished.emit("Flip 중지됨.")
                return

            # 전체 이미지 수 미리 계산
            image_files = [f for f in os.listdir(source)
                           if os.path.isfile(os.path.join(source, f)) and
                           any(f.lower().endswith(fmt.lower()) for fmt in formats)]
            total_images = len(image_files)
            total_processed_images = 0

            self.log.emit(f"Flip Direction: {flip_direction}")

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for file_name in image_files:
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    src_file = os.path.join(source, file_name)
                    dst_file = os.path.join(target, file_name)
                    futures.append(executor.submit(self.flip_image, src_file, dst_file, flip_direction))

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result:
                        total_processed_images += 1
                        self.log.emit(result)
                        # 전체 진행률을 업데이트하기 위해 계산
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

            self.finished.emit(f"Flip 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ Flip 작업 완료 ------")
        except Exception as e:
            logging.error("Flip 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Flip 중 오류 발생.")

    def rotate_images(self, task):
        self.log.emit("------ Rotate 작업 시작 ------")
        try:
            # Rotate 관련 작업 구현
            # 이 예제에서는 단순히 파일을 복사하는 것으로 가정
            source = task['source']
            target = task['target']
            formats = task['formats']
            rotate_angle = task['rotate_angle']  # 예: "90", "180"

            if not os.path.exists(source):
                self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                self.finished.emit("Rotate 중지됨.")
                return
            if not os.path.exists(target):
                os.makedirs(target)

            try:
                angle = float(rotate_angle)
            except Exception as e:
                self.log.emit(f"Rotate Angle 형식 오류: {str(e)}")
                self.finished.emit("Rotate 중지됨.")
                return

            # 전체 이미지 수 미리 계산
            image_files = [f for f in os.listdir(source) if any(f.lower().endswith(fmt.lower()) for fmt in formats)]
            total_images = len(image_files)
            total_processed_images = 0

            self.log.emit(f"Rotate Angle: {angle} degrees")

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for file_name in image_files:
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    src_file = os.path.join(source, file_name)
                    dst_file = os.path.join(target, file_name)
                    futures.append(executor.submit(self.rotate_image, src_file, dst_file, angle))

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 이미지: {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result:
                        total_processed_images += 1
                        self.log.emit(result)
                        # 전체 진행률을 업데이트하기 위해 계산
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))  # 100% 초과 방지

            self.finished.emit(f"Rotate 완료. 총 처리한 이미지: {total_processed_images}")
            self.log.emit("------ Rotate 작업 완료 ------")
        except Exception as e:
            logging.error("Rotate 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Rotate 중 오류 발생.")

    def copy_file(self, src, dst):
        try:
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                while True:
                    buf = fsrc.read(1024 * 1024)  # 1MB 청크 단위로 읽기
                    if not buf:
                        break
                    fdst.write(buf)
            shutil.copystat(src, dst)
            return f"Copied {src} to {dst}"
        except Exception as e:
            logging.error("파일 복사 중 오류", exc_info=True)
            # 복사 도중 오류가 발생하면 부분적으로 복사된 파일을 삭제
            if os.path.exists(dst):
                os.remove(dst)
            return f"오류 발생: {str(e)}"


    def copy_folder(self, src, dst):
        try:
            # Target Path에 이미 같은 이름의 폴더가 존재하면 삭제 (덮어쓰기)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            os.makedirs(dst)
            for root, dirs, files in os.walk(src):
                # 폴더 단위로 Stop 신호 확인
                if self._is_stopped:
                    return f"Copy stopped: {src}"
                # 상대 경로 계산
                rel_path = os.path.relpath(root, src)
                dst_root = os.path.join(dst, rel_path)
                if not os.path.exists(dst_root):
                    os.makedirs(dst_root)
                for file in files:
                    # 파일 단위로 Stop 신호 확인
                    if self._is_stopped:
                        return f"Copy stopped: {src}"
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(dst_root, file)
                    result = self.copy_file(src_file, dst_file)
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        self.log.emit(result)
            shutil.copystat(src, dst)
            return f"Copied folder {src} to {dst}"
        except Exception as e:
            logging.error("폴더 복사 중 오류", exc_info=True)
            return f"오류 발생: {str(e)}"


    def crop_image(self, src, dst, crop_coords):
        try:
            from PIL import Image
            with Image.open(src) as img:
                cropped_img = img.crop(crop_coords)
                cropped_img.save(dst)
            return f"Cropped {src} to {dst}"
        except Exception as e:
            logging.error("이미지 크롭 중 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    def resize_image(self, src, dst, width, height):
        try:
            from PIL import Image
            with Image.open(src) as img:
                resized_img = img.resize((width, height))
                resized_img.save(dst)
            return f"Resized {src} to {dst}"
        except Exception as e:
            logging.error("이미지 리사이즈 중 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    def flip_image(self, src, dst, flip_direction):
        try:
            from PIL import Image
            with Image.open(src) as img:
                if flip_direction.lower() == 'horizontal':
                    flipped_img = img.transpose(Image.FLIP_LEFT_RIGHT)
                elif flip_direction.lower() == 'vertical':
                    flipped_img = img.transpose(Image.FLIP_TOP_BOTTOM)
                else:
                    return f"잘못된 Flip Direction: {flip_direction}"
                flipped_img.save(dst)
            return f"Flipped {src} to {dst}"
        except Exception as e:
            logging.error("이미지 Flip 중 오류 발생", exc_info=True)
            return f"오류 발생: {str(e)}"

    def rotate_image(self, src, dst, angle):
        try:
            from PIL import Image
            with Image.open(src) as img:
                rotated_img = img.rotate(angle, expand=True)
                rotated_img.save(dst)
            return f"Rotated {src} to {dst} by {angle} degrees"
        except Exception as e:
            logging.error("이미지 Rotate 중 오류 발생", exc_info=True)
            return f"오류 발생: {str(e)}"


class BaseTaskDialog(QDialog):
    def __init__(self, title):
        super().__init__()
        self.setWindowTitle(title)
        self.setFixedSize(800, 800)
        self.worker = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Placeholder for specific input fields
        self.specific_layout = QFormLayout()
        form_layout.addRow(self.specific_layout)

        # Image Formats (if needed) - Removed from BaseTaskDialog
        # 이동: 필요한 다이얼로그에서만 Image Formats를 추가

        layout.addLayout(form_layout)

        # Log Area and Buttons
        log_layout = QHBoxLayout()
        log_label = QLabel("<b>Logs:</b>")
        self.clear_log_button = QPushButton("Clear")
        self.clear_log_button.clicked.connect(self.clear_logs)
        log_layout.addWidget(log_label)
        log_layout.addStretch()
        log_layout.addWidget(self.clear_log_button)
        layout.addLayout(log_layout)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #F5F5F5;
                font-family: Consolas;
                font-size: 14px;
                padding: 10px;
                border: 1px solid #CCC;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.log_area)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)  # 0~100%으로 설정
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 10px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #8B0000;
                width: 20px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Buttons (Start and Stop)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_task)
        self.start_button.setStyleSheet("background-color: #8B0000; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #A9A9A9; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def append_log(self, message):
        self.log_area.append(message)

    def clear_logs(self):
        self.log_area.clear()

    def start_task(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "작업 중", "이미 작업이 진행 중입니다.")
            return
        self.log_area.append("------ 작업 시작 ------")
        self.progress_bar.setValue(0)
        params = self.get_parameters()
        if not self.validate_parameters(params):
            self.log_area.append("------ 작업 중지 ------")
            return
        self.worker = WorkerThread(params)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.append_log)
        # NG Count의 경우 별도의 시그널을 처리
        if params.get('operation') == 'ng_count':
            self.worker.ng_count_result.connect(self.update_ng_count_table)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("Stop 신호를 보냈습니다.")
            self.stop_button.setEnabled(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def task_finished(self, message):
        self.append_log(message)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if "완료" in message or "오류" in message or "중지" in message:
            self.append_log("------ 작업 종료 ------")

    def validate_parameters(self, params):
        # 기본 유효성 검증을 수행하고, 필요 시 오버라이드
        missing_fields = []
        # Date-Based Copy는 Inner ID와 Image Formats가 필요 없으므로 조건 수정
        operation = params.get('operation', '')
        if operation != 'ng_count':
            if not params.get('source'):
                missing_fields.append("Source Path")
            if not params.get('target'):
                missing_fields.append("Target Path")
        if operation != 'ng_count' and not params.get('formats', []):
            missing_fields.append("Image Formats")
        if operation == 'ng_sorting' and not params.get('source2'):
            missing_fields.append("Source Path #2 (Matching Folder)")
        if operation == 'ng_count' and not params.get('ng_folder', ''):
            missing_fields.append("NG 폴더를 선택해야 합니다.")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True

    def get_parameters(self):
        # 각 기능별로 오버라이드하여 파라미터를 반환
        return {}

    def update_ng_count_table(self, data):
        # 기본 다이얼로그에서는 구현하지 않음
        pass


# 각 기능별 Dialog 클래스는 BaseTaskDialog를 상속받아 구현
class BasicSortingDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Basic Sorting 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Inner ID List Path
        self.inner_id_list_button = QPushButton("Select Inner ID List Path")
        self.inner_id_list_button.clicked.connect(self.select_inner_id_list)
        self.inner_id_list_path = QLineEdit()
        self.inner_id_list_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Inner ID List Path:</b>"), self.inner_id_list_button)
        self.specific_layout.addRow("", self.inner_id_list_path)

        # Source Path
        self.source_button = QPushButton("Select Matching Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # FOV Number
        self.fov_input = QLineEdit()
        self.fov_input.setPlaceholderText("Enter FOV Number(s), separated by commas (e.g., 1,2,3)")
        self.specific_layout.addRow(QLabel("<b>FOV Number(s):</b>"), self.fov_input)

        # Inner ID (Optional)
        self.inner_id_checkbox = QCheckBox("Use Inner ID")
        self.inner_id_checkbox.stateChanged.connect(self.toggle_inner_id)
        self.specific_layout.addRow(QLabel("<b>Inner ID:</b>"), self.inner_id_checkbox)

        self.inner_id_input = QLineEdit()
        self.inner_id_input.setPlaceholderText("Enter Inner ID")
        self.inner_id_input.setEnabled(False)
        self.specific_layout.addRow("", self.inner_id_input)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def toggle_inner_id(self, state):
        if state == Qt.Checked:
            self.inner_id_input.setEnabled(True)
            self.inner_id_list_path.setEnabled(False)
            self.inner_id_list_button.setEnabled(False)
            self.inner_id_list_path.clear()
        else:
            self.inner_id_input.setEnabled(False)
            self.inner_id_input.clear()
            self.inner_id_list_path.setEnabled(True)
            self.inner_id_list_button.setEnabled(True)

    def select_inner_id_list(self):
        inner_id_list = QFileDialog.getExistingDirectory(self, "Select Inner ID List Path", "",
                                                          QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if inner_id_list:
            self.inner_id_list_path.setText(inner_id_list)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def get_parameters(self):
        # 이미지 포맷 필터링
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'basic_sorting',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'inner_id_list': self.inner_id_list_path.text(),
            'use_inner_id': self.inner_id_checkbox.isChecked(),
            'inner_id': self.inner_id_input.text(),
            'fov_number': self.fov_input.text(),
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['inner_id_list'] and not params['use_inner_id']:
            missing_fields.append("Inner ID List Path 또는 Inner ID")
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['fov_number']:
            missing_fields.append("FOV Number(s)")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")

        if not params['inner_id_list'] and params['use_inner_id'] and not params['inner_id']:
            missing_fields.append("Inner ID")

        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class NGSortingDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("NG Folder Sorting 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Source Path #1 (NG Folders)
        self.add_source_button = QPushButton("Add NG Folder")
        self.add_source_button.clicked.connect(self.add_source_folder)
        self.source1_list = QListWidget()
        self.source1_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.specific_layout.addRow(QLabel("<b>Source Path #1 (NG Folders):</b>"), self.add_source_button)
        self.specific_layout.addRow("", self.source1_list)

        # Remove Selected Folder Button
        self.remove_source_button = QPushButton("Remove Selected Folder")
        self.remove_source_button.clicked.connect(self.remove_selected_source_folder)
        self.specific_layout.addRow("", self.remove_source_button)

        # Source Path #2 (Matching Folder)
        self.source2_button = QPushButton("Select Matching Folder")
        self.source2_button.clicked.connect(self.select_source2)
        self.source2_path = QLineEdit()
        self.source2_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Source Path #2 (Matching Folder):</b>"), self.source2_button)
        self.specific_layout.addRow("", self.source2_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def add_source_folder(self):
        parent_folder = QFileDialog.getExistingDirectory(self, "Select Parent Folder", "",
                                                         QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if parent_folder:
            # 소스 폴더 내의 모든 서브 폴더(OK, NG 제외) 가져오기
            try:
                subfolders = [f for f in os.listdir(parent_folder)
                              if os.path.isdir(os.path.join(parent_folder, f)) and f.lower() not in ['ok', 'ng']]
                if not subfolders:
                    QMessageBox.information(self, "정보", "선택한 폴더 내에 서브 폴더가 없습니다.")
                    return
            except Exception as e:
                logging.error("서브 폴더 목록 가져오기 중 오류", exc_info=True)
                QMessageBox.warning(self, "오류", f"서브 폴더 목록 가져오기 중 오류가 발생했습니다:\n{str(e)}")
                return

            # 서브 폴더 선택 다이얼로그 열기
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Subfolders")
            dialog.setFixedSize(600, 400)
            dialog_layout = QVBoxLayout()

            table_widget = QTableWidget()
            table_widget.setRowCount(len(subfolders))
            table_widget.setColumnCount(2)
            table_widget.setHorizontalHeaderLabels(["Folder Name", "Last Modified Date"])
            table_widget.setSelectionBehavior(QTableWidget.SelectRows)
            table_widget.setSelectionMode(QTableWidget.MultiSelection)
            table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
            table_widget.setSortingEnabled(True)
            table_widget.horizontalHeader().setStretchLastSection(True)
            table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            for row, folder in enumerate(subfolders):
                folder_name_item = QTableWidgetItem(folder)
                folder_name_item.setFlags(folder_name_item.flags() ^ Qt.ItemIsEditable)
                table_widget.setItem(row, 0, folder_name_item)

                folder_path = os.path.join(parent_folder, folder)
                try:
                    modified_timestamp = os.path.getmtime(folder_path)
                    modified_datetime = datetime.fromtimestamp(modified_timestamp)
                    modified_str = modified_datetime.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    modified_str = "N/A"
                    logging.error("폴더 수정 시간 가져오기 중 오류", exc_info=True)
                date_item = QTableWidgetItem(modified_str)
                date_item.setFlags(date_item.flags() ^ Qt.ItemIsEditable)
                table_widget.setItem(row, 1, date_item)

            dialog_layout.addWidget(QLabel("Select subfolders to add:"))
            dialog_layout.addWidget(table_widget)

            button_layout = QHBoxLayout()
            ok_button = QPushButton("OK")
            cancel_button = QPushButton("Cancel")
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            dialog_layout.addLayout(button_layout)

            dialog.setLayout(dialog_layout)

            if dialog.exec_() == QDialog.Accepted:
                selected_rows = table_widget.selectionModel().selectedRows()
                selected_subfolders = [table_widget.item(row.row(), 0).text() for row in selected_rows]
                for sub in selected_subfolders:
                    full_path = os.path.join(parent_folder, sub)
                    # 중복된 폴더는 추가하지 않음
                    existing_items = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
                    if full_path not in existing_items:
                        self.source1_list.addItem(full_path)
                    else:
                        QMessageBox.information(self, "정보", f"이미 추가된 폴더입니다:\n{full_path}")

    def remove_selected_source_folder(self):
        selected_items = self.source1_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "선택 오류", "제거할 폴더를 선택하세요.")
            return
        for item in selected_items:
            self.source1_list.takeItem(self.source1_list.row(item))

    def select_source2(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Matching Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder:
            self.source2_path.setText(folder)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        sources1 = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
        source2 = self.source2_path.text()
        target = self.target_path.text()
        # Image Formats는 개별 다이얼로그에서 처리
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")
        return {
            'operation': 'ng_sorting',
            'inputs': sources1,
            'source2': source2,
            'target': target,
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['inputs']:
            missing_fields.append("Source Path #1에 최소 하나의 폴더를 추가해야 합니다.")
        if not params['source2']:
            missing_fields.append("Source Path #2를 선택해야 합니다.")
        if not params['target']:
            missing_fields.append("Target Path를 선택해야 합니다.")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class DateBasedCopyDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Date-Based Copy 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Date and Time 선택을 위한 QDateTimeEdit 위젯 추가
        self.datetime_edit = QDateTimeEdit(self)
        self.datetime_edit.setCalendarPopup(True)  # 달력 팝업 활성화
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.specific_layout.addRow(QLabel("<b>Date and Time:</b>"), self.datetime_edit)

        # Count
        self.count_input = QSpinBox()
        self.count_input.setRange(1, 1000)
        self.count_input.setValue(1)
        self.specific_layout.addRow(QLabel("<b>Number of Folders to Copy:</b>"), self.count_input)

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def get_parameters(self):
        # QDateTimeEdit에서 날짜와 시간 가져오기
        datetime_qt = self.datetime_edit.dateTime()
        specified_datetime = datetime_qt.toPyDateTime()

        return {
            'operation': 'date_copy',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'year': specified_datetime.year,
            'month': specified_datetime.month,
            'day': specified_datetime.day,
            'hour': specified_datetime.hour,
            'minute': specified_datetime.minute,
            'second': specified_datetime.second,
            'count': self.count_input.value()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['count']:
            missing_fields.append("Number of Folders to Copy")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class ImageFormatCopyDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Image Format Copy 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        # 이미지 포맷 필터링
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'image_copy',
            'sources': [self.source_path.text()],
            'targets': [self.target_path.text()],
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['sources'][0]:
            missing_fields.append("Source Path")
        if not params['targets'][0]:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class SimulationFolderingDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Simulation Foldering 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        # 이미지 포맷 필터링
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'simulation_foldering',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class NGCountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NG Count 설정")
        self.setFixedSize(800, 600)
        self.worker = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # NG Folder Path
        self.ng_folder_button = QPushButton("Select NG Folder")
        self.ng_folder_button.clicked.connect(self.select_ng_folder)
        self.ng_folder_path = QLineEdit()
        self.ng_folder_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Counting - Select NG folder:</b>"), self.ng_folder_button)
        form_layout.addRow("", self.ng_folder_path)

        layout.addLayout(form_layout)

        # NG Count Results with Copy button
        ng_count_results_layout = QHBoxLayout()
        ng_count_label = QLabel("<b>NG Count Results:</b>")
        self.copy_button = QPushButton("Copy")
        self.copy_button.setFixedSize(60, 25)  # 작은 크기로 설정
        self.copy_button.clicked.connect(self.copy_table_to_clipboard)
        ng_count_results_layout.addWidget(ng_count_label)
        ng_count_results_layout.addStretch()
        ng_count_results_layout.addWidget(self.copy_button)
        layout.addLayout(ng_count_results_layout)

        # Table to display NG Count results
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["CamNum", "Defect Name", "Count"])
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_widget)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)  # 0~100%으로 설정
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 10px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #8B0000;
                width: 20px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Buttons (Start and Stop)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_task)
        self.start_button.setStyleSheet("background-color: #8B0000; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #A9A9A9; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def select_ng_folder(self):
        ng_folder = QFileDialog.getExistingDirectory(self, "Select NG Folder", "",
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if ng_folder:
            self.ng_folder_path.setText(ng_folder)

    def start_task(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "작업 중", "이미 작업이 진행 중입니다.")
            return
        self.table_widget.setRowCount(0)  # 기존 표 초기화
        self.progress_bar.setValue(0)
        ng_folder = self.ng_folder_path.text()
        if not ng_folder:
            QMessageBox.warning(self, "입력 오류", "NG 폴더를 선택해야 합니다.")
            return
        task = {'operation': 'ng_count', 'ng_folder': ng_folder}
        self.worker = WorkerThread(task)
        self.worker.progress.connect(self.update_progress)
        self.worker.ng_count_result.connect(self.update_ng_count_table)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("Stop 신호를 보냈습니다.")
            self.stop_button.setEnabled(False)

    def append_log(self, message):
        # NG Count에서는 로그를 사용하지 않음
        pass

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_ng_count_table(self, data):
        self.table_widget.setRowCount(len(data))
        for row, (cam, defect, count) in enumerate(data):
            cam_item = QTableWidgetItem(cam)
            defect_item = QTableWidgetItem(defect)
            count_item = QTableWidgetItem(str(count))
            self.table_widget.setItem(row, 0, cam_item)
            self.table_widget.setItem(row, 1, defect_item)
            self.table_widget.setItem(row, 2, count_item)

    def task_finished(self, message):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        QMessageBox.information(self, "작업 완료", message)

    def copy_table_to_clipboard(self):
        if self.table_widget.rowCount() == 0:
            QMessageBox.warning(self, "복사 오류", "복사할 데이터가 없습니다.")
            return
        clipboard = QApplication.clipboard()
        data = []
        headers = [self.table_widget.horizontalHeaderItem(i).text() for i in range(self.table_widget.columnCount())]
        data.append('\t'.join(headers))
        for row in range(self.table_widget.rowCount()):
            row_data = []
            for column in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, column)
                if item is not None:
                    row_data.append(item.text())
                else:
                    row_data.append('')
            data.append('\t'.join(row_data))
        clipboard.setText('\n'.join(data))
        QMessageBox.information(self, "복사 완료", "표가 클립보드에 복사되었습니다.")


class CropDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Crop 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Crop 관련 설정을 여기에 추가
        self.specific_layout.addRow(QLabel("<b>Crop Area:</b>"))
        self.crop_area_input = QLineEdit()
        self.crop_area_input.setPlaceholderText("Enter crop area parameters (left, upper, right, lower)")
        self.specific_layout.addRow("", self.crop_area_input)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'crop',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats,
            'crop_area': self.crop_area_input.text()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")
        if not params['crop_area']:
            missing_fields.append("Crop Area Parameters")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class ResizeDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Resize 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Resize 관련 설정을 여기에 추가
        self.specific_layout.addRow(QLabel("<b>Resize Dimensions:</b>"))
        self.resize_dim_input = QLineEdit()
        self.resize_dim_input.setPlaceholderText("Enter dimensions (e.g., 800x600)")
        self.specific_layout.addRow("", self.resize_dim_input)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'resize',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats,
            'resize_dimensions': self.resize_dim_input.text()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")
        if not params['resize_dimensions']:
            missing_fields.append("Resize Dimensions")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class FlipDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("FLIP 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Flip 관련 설정을 여기에 추가
        self.specific_layout.addRow(QLabel("<b>Flip Direction:</b>"))
        self.flip_direction_input = QLineEdit()
        self.flip_direction_input.setPlaceholderText("Enter flip direction (e.g., horizontal, vertical)")
        self.specific_layout.addRow("", self.flip_direction_input)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'flip',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats,
            'flip_direction': self.flip_direction_input.text()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")
        if not params['flip_direction']:
            missing_fields.append("Flip Direction")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class RotateDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Rotate 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Rotate 관련 설정을 여기에 추가
        self.specific_layout.addRow(QLabel("<b>Rotate Angle:</b>"))
        self.rotate_angle_input = QLineEdit()
        self.rotate_angle_input.setPlaceholderText("Enter rotate angle (e.g., 90, 180)")
        self.specific_layout.addRow("", self.rotate_angle_input)

        # Image Formats 추가 (BaseTaskDialog에서 제거됨)
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'rotate',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats,
            'rotate_angle': self.rotate_angle_input.text()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")
        if not params['rotate_angle']:
            missing_fields.append("Rotate Angle")
        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AiV File Processor🖥️")

        # 아이콘 경로 수정
        if getattr(sys, 'frozen', False):
            # 실행 파일로 패키징된 경우 (PyInstaller)
            application_path = sys._MEIPASS
        else:
            # 개발 중인 경우
            application_path = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(application_path, 'AiV.ico')  # 'AiV.ico'로 변경
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # 아이콘 파일이 없을 경우 기본 아이콘 사용
            pass

        self.setFixedSize(1000, 300)
        self.initUI()
        self.dialogs = {}  # 열린 Dialog를 저장할 딕셔너리 생성

    def initUI(self):
        main_layout = QVBoxLayout()

        # Buttons for each functionality in 2 rows of 5
        button_layout = QGridLayout()
        button_layout.setSpacing(20)  # 버튼 간 간격 설정

        # Button 스타일 설정 함수
        def button_style():
            return """
                QPushButton {
                    background-color: #8B0000;
                    color: white;
                    font-size: 14px;
                    border: 2px solid black;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #A52A2A;
                }
            """

        # First Row Buttons
        self.ng_sorting_button = QPushButton("NG Folder Sorting")
        self.ng_sorting_button.clicked.connect(self.open_ng_sorting)
        self.ng_sorting_button.setFixedSize(150, 80)
        self.ng_sorting_button.setStyleSheet(button_style())
        button_layout.addWidget(self.ng_sorting_button, 0, 0)

        self.date_copy_button = QPushButton("Date-Based Copy")
        self.date_copy_button.clicked.connect(self.open_date_copy)
        self.date_copy_button.setFixedSize(150, 80)
        self.date_copy_button.setStyleSheet(button_style())
        button_layout.addWidget(self.date_copy_button, 0, 1)

        self.image_copy_button = QPushButton("Image Format Copy")
        self.image_copy_button.clicked.connect(self.open_image_copy)
        self.image_copy_button.setFixedSize(150, 80)
        self.image_copy_button.setStyleSheet(button_style())
        button_layout.addWidget(self.image_copy_button, 0, 2)

        self.basic_sorting_button = QPushButton("Basic Sorting")
        self.basic_sorting_button.clicked.connect(self.open_basic_sorting)
        self.basic_sorting_button.setFixedSize(150, 80)
        self.basic_sorting_button.setStyleSheet(button_style())
        button_layout.addWidget(self.basic_sorting_button, 0, 3)

        self.ng_count_button = QPushButton("NG Count")
        self.ng_count_button.clicked.connect(self.open_ng_count)
        self.ng_count_button.setFixedSize(150, 80)
        self.ng_count_button.setStyleSheet(button_style())
        button_layout.addWidget(self.ng_count_button, 0, 4)

        # Second Row Buttons
        self.simulation_button = QPushButton("Simulation Foldering")
        self.simulation_button.clicked.connect(self.open_simulation_foldering)
        self.simulation_button.setFixedSize(150, 80)
        self.simulation_button.setStyleSheet(button_style())
        button_layout.addWidget(self.simulation_button, 1, 0)

        self.crop_button = QPushButton("Crop")
        self.crop_button.clicked.connect(self.open_crop)
        self.crop_button.setFixedSize(150, 80)
        self.crop_button.setStyleSheet(button_style())
        button_layout.addWidget(self.crop_button, 1, 1)

        self.resize_button = QPushButton("Resize")
        self.resize_button.clicked.connect(self.open_resize)
        self.resize_button.setFixedSize(150, 80)
        self.resize_button.setStyleSheet(button_style())
        button_layout.addWidget(self.resize_button, 1, 2)

        self.flip_button = QPushButton("FLIP")
        self.flip_button.clicked.connect(self.open_flip)
        self.flip_button.setFixedSize(150, 80)
        self.flip_button.setStyleSheet(button_style())
        button_layout.addWidget(self.flip_button, 1, 3)

        self.rotate_button = QPushButton("Rotate")
        self.rotate_button.clicked.connect(self.open_rotate)
        self.rotate_button.setFixedSize(150, 80)
        self.rotate_button.setStyleSheet(button_style())
        button_layout.addWidget(self.rotate_button, 1, 4)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    # 각 Dialog 열기 메서드 수정
    def open_ng_sorting(self):
        if 'ng_sorting' not in self.dialogs:
            self.dialogs['ng_sorting'] = NGSortingDialog()
            self.dialogs['ng_sorting'].finished.connect(lambda: self.dialogs.pop('ng_sorting', None))
        self.dialogs['ng_sorting'].show()

    def open_ng_count(self):
        if 'ng_count' not in self.dialogs:
            self.dialogs['ng_count'] = NGCountDialog()
            self.dialogs['ng_count'].finished.connect(lambda: self.dialogs.pop('ng_count', None))
        self.dialogs['ng_count'].show()

    def open_date_copy(self):
        if 'date_copy' not in self.dialogs:
            self.dialogs['date_copy'] = DateBasedCopyDialog()
            self.dialogs['date_copy'].finished.connect(lambda: self.dialogs.pop('date_copy', None))
        self.dialogs['date_copy'].show()

    def open_image_copy(self):
        if 'image_copy' not in self.dialogs:
            self.dialogs['image_copy'] = ImageFormatCopyDialog()
            self.dialogs['image_copy'].finished.connect(lambda: self.dialogs.pop('image_copy', None))
        self.dialogs['image_copy'].show()

    def open_simulation_foldering(self):
        if 'simulation_foldering' not in self.dialogs:
            self.dialogs['simulation_foldering'] = SimulationFolderingDialog()
            self.dialogs['simulation_foldering'].finished.connect(lambda: self.dialogs.pop('simulation_foldering', None))
        self.dialogs['simulation_foldering'].show()

    def open_basic_sorting(self):
        if 'basic_sorting' not in self.dialogs:
            self.dialogs['basic_sorting'] = BasicSortingDialog()
            self.dialogs['basic_sorting'].finished.connect(lambda: self.dialogs.pop('basic_sorting', None))
        self.dialogs['basic_sorting'].show()

    def open_crop(self):
        if 'crop' not in self.dialogs:
            self.dialogs['crop'] = CropDialog()
            self.dialogs['crop'].finished.connect(lambda: self.dialogs.pop('crop', None))
        self.dialogs['crop'].show()

    def open_resize(self):
        if 'resize' not in self.dialogs:
            self.dialogs['resize'] = ResizeDialog()
            self.dialogs['resize'].finished.connect(lambda: self.dialogs.pop('resize', None))
        self.dialogs['resize'].show()

    def open_flip(self):
        if 'flip' not in self.dialogs:
            self.dialogs['flip'] = FlipDialog()
            self.dialogs['flip'].finished.connect(lambda: self.dialogs.pop('flip', None))
        self.dialogs['flip'].show()

    def open_rotate(self):
        if 'rotate' not in self.dialogs:
            self.dialogs['rotate'] = RotateDialog()
            self.dialogs['rotate'].finished.connect(lambda: self.dialogs.pop('rotate', None))
        self.dialogs['rotate'].show()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Palette 설정을 통해 다크 레드, 회색, 흰색 사용
    palette = app.palette()
    palette.setColor(palette.Window, Qt.white)
    palette.setColor(palette.Button, Qt.darkGray)
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.Base, Qt.white)
    palette.setColor(palette.Text, Qt.black)
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
