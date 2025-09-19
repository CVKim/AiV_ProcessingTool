# worker.py
import os
import shutil
import logging
import random
import re
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtCore import QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from datetime import datetime

import json

from PIL import Image, ImageOps, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True  

logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def set_worker_priority():
    try:
        import win32api, win32process, win32con
        thread_handle = win32api.GetCurrentThread()
        win32process.SetThreadPriority(thread_handle, win32process.THREAD_PRIORITY_BELOW_NORMAL)
    except ImportError:
        try:
            os.nice(10)  # default 0, range -20 ~ 19
        except Exception:
            pass

class WorkerThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    ng_count_result = pyqtSignal(object)
    finished = pyqtSignal(str)

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._is_stopped = False
        self.max_workers = min(12, (multiprocessing.cpu_count() or 1) * 2)

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
            elif operation == 'attach_fov':
                self.attach_fov(self.task)
            elif operation == 'mim_to_bmp':
                self.mim_to_bmp(self.task)
            elif operation == 'btj':
                self.btj_operation(self.task)
            else:
                self.log.emit("알 수 없는 작업 유형입니다.")
                self.finished.emit("알 수 없는 작업 유형입니다.")
        except Exception as e:
            logging.error("작업 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중 오류 발생했습니다.")

    def stop(self):
        self._is_stopped = True

    ########################################################################
    # 타겟 폴더 자동 생성 함수
    ########################################################################
    def ensure_target_folder(self, target_path):
        if not os.path.exists(target_path):
            try:
                os.makedirs(target_path)
                self.log.emit(f"Target 경로 생성: {target_path}")
            except Exception as e:
                self.log.emit(f"Target 경로 생성 실패: {target_path} | 에러: {e}")
                return False
        return True

    ########################################################################
    # 헬퍼 함수: 특정 폴더에서 FOV 매칭 파일 목록 반환
    ########################################################################
    def _get_matching_files_for_folder(self, folder_path, formats, fov_numbers):
            """
            주어진 folder_path를 스캔하여, fov_numbers에 포함되는 파일을 반환.
            """
            if not os.path.isdir(folder_path):
                return []
            try:
                with os.scandir(folder_path) as it:
                    image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                
                matching_files = []
                for fname in image_files:
                    parts = fname.split('_', 1)
                    if len(parts) < 1:
                        continue
                    prefix = parts[0].lower()
                    numeric_part = re.sub(r'[^0-9]', '', prefix)
                    if numeric_part in fov_numbers:
                        matching_files.append(fname)
                return matching_files
            except Exception as e:
                self.log.emit(f"이미지 목록 오류: {folder_path} | 에러: {e}")
                return []

    ########################################################################
    # 1) NG Folder Sorting
    ########################################################################
    def ng_folder_sorting(self, task):
        
        self.log.emit("------ NG Folder Sorting 작업 시작 ------")
        try:
            sources1 = task.get('inputs', [])
            source2 = task.get('source2', '')
            target = task.get('target', '')
            formats = task.get('formats', [])
            self.log.emit(f"Sources1: {sources1}")
            self.log.emit(f"Source2: {source2}")
            self.log.emit(f"Target: {target}")
            self.log.emit(f"Formats: {formats}")
            if not self.ensure_target_folder(target):
                self.finished.emit("NG Folder Sorting 중단.")
                return
            inner_ids_sources1 = self.collect_inner_ids(sources1)
            inner_ids_source2 = self.collect_inner_ids_from_source2(source2)
            matched_inner_ids = inner_ids_sources1.intersection(inner_ids_source2)
            total_matched_inner_ids = len(matched_inner_ids)
            if total_matched_inner_ids == 0:
                self.log.emit("sources1과 source2 모두에 존재하는 Inner ID가 없습니다.")
                self.finished.emit("NG Folder Sorting 완료.")
                return
            self.log.emit(f"총 매칭된 Inner ID 수: {total_matched_inner_ids}")
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
                        self.log.emit(f"작업 중지: 처리한 이미지 {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 처리한 이미지: {total_processed_images}")
                        return
                    source_inner_id_folder = os.path.join(source2, inner_id)
                    target_inner_id_folder = os.path.join(target, inner_id)
                    if not self.ensure_target_folder(target_inner_id_folder):
                        continue
                    for image in images:
                        if self._is_stopped:
                            self.log.emit(f"작업 중지: 처리한 이미지 {total_processed_images}")
                            self.finished.emit(f"작업 중지됨. 처리한 이미지: {total_processed_images}")
                            return
                        src_file = os.path.join(source_inner_id_folder, image)
                        dst_file = os.path.join(target_inner_id_folder, image)
                        if os.path.exists(dst_file):
                            self.log.emit(f"파일 건너뜀: {dst_file}")
                            continue
                        future = executor.submit(self.copy_file_chunked, src_file, dst_file)
                        futures[future] = (src_file, dst_file)
                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 처리한 이미지 {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 처리한 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        total_processed_images += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))
            self.finished.emit(f"NG Folder Sorting 완료. 처리한 이미지: {total_processed_images}")
            self.log.emit("------ NG Folder Sorting 작업 완료 ------")
        except Exception as e:
            logging.error("NG Folder Sorting 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("NG Folder Sorting 중 오류 발생.")

    ########################################################################
    # 2) Date-Based Copy (Optimized for faster execution)
    ########################################################################
    def date_based_copy(self, task):
        # (기존 코드 동일)
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
                self.log.emit(f"Source 경로 없음: {source}")
                self.finished.emit("Date-Based Copy 중지됨.")
                return
            if not self.ensure_target_folder(target):
                self.finished.emit("Date-Based Copy 중지됨.")
                return
            all_folders = [os.path.join(source, f) for f in os.listdir(source)
                           if os.path.isdir(os.path.join(source, f))]
            eligible_folders = []
            for folder in all_folders:
                try:
                    folder_mtime = datetime.fromtimestamp(os.path.getmtime(folder))
                    if folder_mtime >= specified_datetime:
                        eligible_folders.append(folder)
                except Exception as e:
                    self.log.emit(f"폴더 {folder} 수정시간 오류: {str(e)}")
            if not eligible_folders:
                self.log.emit("지정 날짜 이후 폴더 없음")
                self.finished.emit("Date-Based Copy 완료.")
                return
            sorted_folders = sorted(eligible_folders, key=lambda x: os.path.getmtime(x))
            if mode == 'folder':
                if strong_random:
                    self.log.emit("Strong Random (Folder Mode)")
                    selected_folders = sorted_folders if len(sorted_folders) < count else random.sample(sorted_folders, count)
                elif conditional_random:
                    self.log.emit(f"Conditional Random (Folder Mode, Random Count: {random_count})")
                    selected_folders = []
                    index = 0
                    while index < len(sorted_folders) and len(selected_folders) < count:
                        selected_folders.append(sorted_folders[index])
                        index += (random_count + 1)
                else:
                    selected_folders = sorted_folders[:count]
                total_folders = len(selected_folders)
                self.log.emit(f"날짜: {specified_datetime.strftime('%Y-%m-%d %H:%M:%S')}, 폴더 수: {total_folders}")
                total_processed_folders = 0
                with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                    futures = []
                    for folder_path in selected_folders:
                        if self._is_stopped:
                            self.log.emit(f"작업 중지: 폴더 처리 {total_processed_folders}")
                            self.finished.emit(f"작업 중지됨. 폴더 처리: {total_processed_folders}")
                            return
                        folder_name = os.path.basename(folder_path)
                        dst_folder = os.path.join(target, folder_name)
                        if not self.ensure_target_folder(dst_folder):
                            continue
                        self.log.emit(f"Source: {folder_path}, Destination: {dst_folder}")
                        futures.append(executor.submit(self.copy_folder_filtered, folder_path, dst_folder, formats))
                    for future in as_completed(futures):
                        if self._is_stopped:
                            self.log.emit(f"작업 중지: 폴더 처리 {total_processed_folders}")
                            self.finished.emit(f"작업 중지됨. 폴더 처리: {total_processed_folders}")
                            return
                        result = future.result()
                        self.log.emit(result)
                        total_processed_folders += 1
                        progress_percent = int((total_processed_folders / total_folders) * 100)
                        self.progress.emit(min(progress_percent, 100))
                self.finished.emit(f"Date-Based Copy (Folder Mode) 완료. 폴더 처리: {total_processed_folders}")
                self.log.emit("------ Date-Based Copy (Folder Mode) 완료 ------")
            
            elif mode == 'image':
                if not fov_numbers:
                    self.log.emit("Image 모드 FOV Numbers 필수")
                    self.finished.emit("Date-Based Copy 중지됨.")
                    return
                if strong_random:
                    self.log.emit("Strong Random (Image Mode)")
                    selected_folders = sorted_folders if len(sorted_folders) < count else random.sample(sorted_folders, count)
                elif conditional_random:
                    self.log.emit(f"Conditional Random (Image Mode, Random Count: {random_count})")
                    selected_folders = []
                    index = 0
                    while index < len(sorted_folders) and len(selected_folders) < count:
                        selected_folders.append(sorted_folders[index])
                        index += random_count
                else:
                    selected_folders = sorted_folders[:count]
                total_folders = len(selected_folders)
                self.log.emit(f"Image Mode: 선택된 폴더 수 {total_folders}")
                total_processed_folders = 0
                total_processed_images = 0
                for i, folder_path in enumerate(selected_folders, start=1):
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 폴더 처리 {total_processed_folders}")
                        self.finished.emit(f"작업 중지됨. 폴더 처리: {total_processed_folders}")
                        return
                    inner_id = os.path.basename(folder_path)
                    source_inner_id_folder = folder_path
                    try:
                        with os.scandir(source_inner_id_folder) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                    except Exception as e:
                        self.log.emit(f"폴더 {source_inner_id_folder} 파일 목록 오류: {e}")
                        continue
                    matching_images = []
                    for image in image_files:
                        parts = image.split('_', 1)
                        if len(parts) < 2:
                            self.log.emit(f"파일 이름 오류: {image}")
                            continue
                        prefix = parts[0].lower()
                        numeric_part = re.sub(r'[^0-9]', '', prefix)
                        if numeric_part in fov_numbers:
                            matching_images.append(image)
                    if not matching_images:
                        self.log.emit(f"폴더 {source_inner_id_folder} FOV 미일치")
                    else:
                        self.log.emit(f"폴더 {source_inner_id_folder}에서 {len(matching_images)} 이미지 복사 시작")
                        with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                            futures = []
                            for image in matching_images:
                                if self._is_stopped:
                                    break
                                src_file = os.path.join(source_inner_id_folder, image)
                                file_base, file_ext = os.path.splitext(image)
                                new_file_name = f"{inner_id}_{file_base}{file_ext}"
                                dst_file = os.path.join(target, new_file_name)
                                if os.path.exists(dst_file):
                                    self.log.emit(f"파일 건너뜀: {dst_file}")
                                    continue
                                futures.append(executor.submit(self.copy_file_chunked, src_file, dst_file))
                            for future in as_completed(futures):
                                if self._is_stopped:
                                    break
                                result = future.result()
                                if result.startswith("오류 발생"):
                                    self.log.emit(result)
                                else:
                                    total_processed_images += 1
                                    self.log.emit(result)
                    total_processed_folders += 1
                    progress_percent = int((total_processed_folders / total_folders) * 100)
                    self.progress.emit(min(progress_percent, 100))
                self.finished.emit(f"Date-Based Copy (Image Mode) 완료. 폴더: {total_processed_folders}, 이미지: {total_processed_images}")
                self.log.emit("------ Date-Based Copy (Image Mode) 완료 ------")
                
        except Exception as e:
            logging.error("Date-Based Copy 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Date-Based Copy 중 오류 발생.")
            

    ########################################################################
    # 3) Image Format Copy
    ########################################################################
    def image_format_copy(self, task):
        self.log.emit("------ Image Format Copy 작업 시작 ------")
        try:
            sources = task['sources']
            targets = task['targets']
            formats = task['formats']
            
            if not os.path.exists(targets[0]):
                os.makedirs(targets[0])
            
            # if not sources or not targets:
            #     self.log.emit("Source 또는 Target 경로 미설정")
            #     self.finished.emit("Image Format Copy 중지됨.")
            #     return
            total_processed_images = 0
            total_images = 0
            src_target_pairs = list(zip(sources, targets))
            for source, target in src_target_pairs:
                if os.path.exists(source):
                    try:
                        with os.scandir(source) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                    except Exception as e:
                        self.log.emit(f"Source {source} 파일 목록 오류: {e}")
                        continue
                    total_images += len(image_files)
            if total_images == 0:
                self.log.emit("선택한 이미지 포맷 없음")
                self.finished.emit("Image Format Copy 완료.")
                return
            self.log.emit(f"총 복사할 이미지 수: {total_images}")
            processed_count = 0
            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for source, target in src_target_pairs:
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 처리 이미지 {processed_count}")
                        self.finished.emit(f"작업 중지됨. 처리 이미지: {processed_count}")
                        return
                    if not os.path.exists(source):
                        self.log.emit(f"Source 경로 없음: {source}")
                        continue
                    if not self.ensure_target_folder(target):
                        continue
                    try:
                        with os.scandir(source) as it:
                            image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                    except Exception as e:
                        self.log.emit(f"Source {source} 파일 목록 오류: {e}")
                        continue
                    for file_name in image_files:
                        if self._is_stopped:
                            self.log.emit(f"작업 중지: 처리 이미지 {processed_count}")
                            self.finished.emit(f"작업 중지됨. 처리 이미지: {processed_count}")
                            return
                        src_file = os.path.join(source, file_name)
                        dst_file = os.path.join(target, file_name)
                        futures.append(executor.submit(self.copy_file_chunked, src_file, dst_file))
                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 처리 이미지 {processed_count}")
                        self.finished.emit(f"작업 중지됨. 처리 이미지: {processed_count}")
                        return
                    result = future.result()
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        processed_count += 1
                        self.log.emit(result)
                        progress_percent = int((processed_count / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))
            self.finished.emit(f"Image Format Copy 완료. 처리 이미지: {processed_count}")
            self.log.emit("------ Image Format Copy 작업 완료 ------")
        except Exception as e:
            logging.error("Image Format Copy 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Image Format Copy 중 오류 발생.")

    ########################################################################
    # 4) Simulation Foldering
    ########################################################################
    def simulation_foldering(self, task):
        self.log.emit("------ Simulation Foldering 작업 시작 ------")
        self.finished.emit("Simulation Foldering 작업 완료.")
        
    
    ########################################################################
    # 5) NG Count
    ########################################################################
    def ng_count(self, task):
        self.log.emit("------ NG Count 작업 시작 ------")
        try:
            ng_folder = task['ng_folder']
            if not os.path.exists(ng_folder):
                self.log.emit(f"NG 폴더 없음: {ng_folder}")
                self.finished.emit("NG Count 중지됨.")
                return
            try:
                with os.scandir(ng_folder) as it:
                    cam_folders = [entry.name for entry in it if entry.is_dir() and entry.name.startswith('Cam_')]
            except Exception as e:
                self.log.emit(f"Cam_ 폴더 탐색 오류: {e}")
                self.finished.emit("NG Count 중지됨.")
                return
            total_cams = len(cam_folders)
            total_defects = 0
            ng_count_data = []
            if total_cams == 0:
                self.log.emit("NG 폴더 내 Cam_ 폴더 없음")
                self.finished.emit("NG Count 완료.")
                return
            for i, cam in enumerate(cam_folders, start=1):
                if self._is_stopped:
                    self.log.emit(f"작업 중지: Cam {total_cams}, Defect {total_defects}")
                    self.finished.emit(f"작업 중지됨. Cam {total_cams}, Defect {total_defects}")
                    return
                cam_path = os.path.join(ng_folder, cam)
                try:
                    with os.scandir(cam_path) as it:
                        defect_folders = [entry.name for entry in it if entry.is_dir()]
                except Exception as e:
                    self.log.emit(f"Cam {cam_path} Defect 폴더 오류: {e}")
                    continue
                for defect in defect_folders:
                    defect_path = os.path.join(cam_path, defect)
                    try:
                        with os.scandir(defect_path) as it_defect:
                            count = sum(1 for _ in it_defect if _.is_dir())
                        ng_count_data.append([cam, defect, count])
                        total_defects += count
                    except Exception as e:
                        self.log.emit(f"Defect {defect_path} 항목 계산 오류: {e}")
                progress_percent = int((i / total_cams) * 100)
                self.progress.emit(min(progress_percent, 100))
            
            # 추가: NG 폴더의 부모 폴더에서 "ng", "ok", "ng_info"를 제외한 폴더 수를 계산
            parent_folder = os.path.dirname(ng_folder)
            exclude = {'ng', 'ok', 'ng_info'}
            total_top_folders = 0
            if os.path.isdir(parent_folder):
                try:
                    with os.scandir(parent_folder) as it:
                        top_folders = [entry.name for entry in it 
                                       if entry.is_dir() and entry.name.lower() not in exclude]
                    total_top_folders = len(top_folders)
                except Exception as e:
                    self.log.emit(f"상위 폴더 탐색 오류: {e}")
            
            # 결과를 tuple로 emit : (ng_count_data, total_top_folders, total_cams, total_defects)
            self.ng_count_result.emit((ng_count_data, total_top_folders, total_cams, total_defects))
            # self.finished.emit(f"NG Count 완료. Cam Count: {total_cams}, Defect: {total_defects}")
            self.log.emit("------ NG Count 작업 완료 ------")
        except Exception as e:
            logging.error("NG Count 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("NG Count 중 오류 발생.")

            
    ########################################################################
    # 6) Basic Sorting
    ########################################################################
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
                is_double_path = task.get('double_path_folder', False)

                # Inner ID 목록 수집
                inner_id_info = [] # {'path': 'Code/InnerID', 'name': 'InnerID'} 형태의 딕셔너리 리스트
                ignore_list = {'ok', 'ng', 'ng_info', 'crop', 'thumbnail'}

                if use_inner_id and inner_id:
                    inner_id_info.append({'path': inner_id, 'name': inner_id})
                    if is_double_path:
                        self.log.emit("경고: 'Use Inner ID' 직접 입력 시 'Double Path Folder' 옵션은 무시됩니다.")
                elif inner_id_list_path and os.path.isdir(inner_id_list_path):
                    try:
                        with os.scandir(inner_id_list_path) as it:
                            for entry in it:
                                if not entry.is_dir() or entry.name.lower() in ignore_list:
                                    continue
                                
                                if is_double_path:
                                    # Double Path: entry는 Code 폴더, 그 안을 한번 더 탐색
                                    code_folder_path = os.path.join(inner_id_list_path, entry.name)
                                    with os.scandir(code_folder_path) as sub_it:
                                        for sub_entry in sub_it:
                                            if sub_entry.is_dir() and sub_entry.name.lower() not in ignore_list:
                                                rel_path = os.path.join(entry.name, sub_entry.name)
                                                inner_id_info.append({'path': rel_path, 'name': sub_entry.name})
                                else:
                                    # Single Path: entry가 바로 Inner ID 폴더
                                    inner_id_info.append({'path': entry.name, 'name': entry.name})
                    except Exception as e:
                        self.log.emit(f"Inner ID List Path 오류: {str(e)}")
                        self.finished.emit("Basic Sorting 중지됨.")
                        return
                else:
                    self.log.emit("Inner ID List Path가 유효하지 않거나, 직접 입력된 Inner ID가 없습니다.")
                    self.finished.emit("Basic Sorting 중지됨.")
                    return

                if not inner_id_info:
                    self.log.emit("유효한 Inner ID가 없습니다.")
                    self.finished.emit("Basic Sorting 완료.")
                    return

                if fov_number_input:
                    fov_numbers = self.parse_fov_numbers(fov_number_input)
                    if fov_numbers is None:
                        self.log.emit("유효한 FOV Number가 입력되지 않았습니다.")
                        self.finished.emit("Basic Sorting 중지됨.")
                        return

                    if not os.path.exists(source):
                        self.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
                        self.finished.emit("Basic Sorting 중지됨.")
                        return
                    if not self.ensure_target_folder(target):
                        self.finished.emit("Basic Sorting 중지됨.")
                        return

                    folder_to_files = {}
                    with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as scan_executor:
                        future_to_info = {}
                        for info in inner_id_info:
                            src_folder_path = os.path.join(source, info['path'])
                            if os.path.isdir(src_folder_path):
                                # 수정된 함수 호출 방식 적용
                                future = scan_executor.submit(self._get_matching_files_for_folder, src_folder_path, formats, fov_numbers)
                                future_to_info[future] = info
                        
                        for future in as_completed(future_to_info):
                            info = future_to_info[future]
                            matching_files = future.result()
                            if matching_files:
                                folder_to_files[info['path']] = {'files': matching_files, 'name': info['name']}

                    total_images = sum(len(data['files']) for data in folder_to_files.values())
                    if total_images == 0:
                        self.log.emit("선택한 FOV Number에 해당하는 이미지가 없습니다.")
                        self.finished.emit("Basic Sorting 완료.")
                        return

                    total_processed = 0
                    with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as copy_executor:
                        futures = []
                        for rel_path, data in folder_to_files.items():
                            source_folder = os.path.join(source, rel_path)
                            inner_id_name = data['name']
                            for image_file in data['files']:
                                if self._is_stopped: break
                                src_file = os.path.join(source_folder, image_file)
                                file_base, file_ext = os.path.splitext(image_file)
                                new_file_name = f"{inner_id_name}_{file_base}{file_ext}"
                                dst_file = os.path.join(target, new_file_name)
                                futures.append(copy_executor.submit(self.copy_file_chunked, src_file, dst_file))
                            if self._is_stopped: break
                        
                        for future in as_completed(futures):
                            if self._is_stopped: break
                            result = future.result()
                            if not result.startswith("오류 발생"):
                                total_processed += 1
                                self.log.emit(result)
                                progress_percent = int((total_processed / total_images) * 100)
                                self.progress.emit(min(progress_percent, 100))
                    
                    if self._is_stopped:
                        self.finished.emit(f"Basic Sorting 중지됨. ({total_processed}/{total_images})")
                        return
                    
                    self.finished.emit(f"Basic Sorting 완료. 총 처리 파일: {total_processed}")
                    self.log.emit("------ Basic Sorting 작업 완료 ------")
                else:
                    # [FOV 미입력 시] → inner_id_list_path에서 파일 복사 (기존 로직)
                    self.log.emit("FOV 미입력: inner_id_list_path 폴더의 파일 복사 진행")
                    total_images = 0
                    folder_to_files = {}
                    for info in inner_id_info:
                        if self._is_stopped: break
                        source_folder = os.path.join(inner_id_list_path, info['name'])
                        if not os.path.isdir(source_folder):
                            self.log.emit(f"폴더 없음: {source_folder}")
                            continue
                        try:
                            with os.scandir(source_folder) as it:
                                image_files = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                            if image_files:
                                folder_to_files[info['name']] = image_files
                                total_images += len(image_files)
                        except Exception as e:
                            self.log.emit(f"파일 목록 오류: {source_folder} | 에러: {e}")
                    
                    if total_images == 0:
                        self.log.emit("formats 조건에 맞는 파일 없음.")
                        self.finished.emit("Basic Sorting 완료.")
                        return

                    total_processed = 0
                    with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                        futures = []
                        for folder_name, image_files in folder_to_files.items():
                            if self._is_stopped: break
                            source_folder = os.path.join(inner_id_list_path, folder_name)
                            for image_file in image_files:
                                if self._is_stopped: break
                                src_file = os.path.join(source_folder, image_file)
                                new_file_name = f"{folder_name}_{image_file}"
                                dst_file = os.path.join(target, new_file_name)
                                futures.append(executor.submit(self.copy_file_chunked, src_file, dst_file))

                        for future in as_completed(futures):
                            if self._is_stopped: break
                            result = future.result()
                            if not result.startswith("오류 발생"):
                                total_processed += 1
                                progress_percent = int((total_processed / total_images) * 100)
                                self.log.emit(result)
                                self.progress.emit(min(progress_percent, 100))
                    
                    if self._is_stopped:
                        self.finished.emit(f"Basic Sorting 중지됨. ({total_processed}/{total_images})")
                        return

                    self.finished.emit(f"Basic Sorting 완료. 총 처리 파일: {total_processed}")
                    self.log.emit("------ Basic Sorting 작업 완료 ------")
            except Exception as e:
                logging.error("Basic Sorting 중 오류", exc_info=True)
                self.log.emit(f"오류 발생: {str(e)}")
                self.finished.emit("작업 중 오류 발생.")


        ########################################################################
    # 7) Crop
    ########################################################################
    def crop_images(self, task):
        self.log.emit("------ Crop 작업 시작 ------")
        try:
            source = task['source']
            target = task['target']
            formats = task['formats']
            fov_number_input = task.get('fov_number', '').strip()

            # 1) 좌표 파싱 + 모드(ltrb / xywh) 처리
            try:
                x1 = int(task['left_top_x'])
                y1 = int(task['left_top_y'])
                x2 = int(task['right_bottom_x'])
                y2 = int(task['right_bottom_y'])

                coords_mode = task.get('coords_mode', 'ltrb')  # 'xywh' or 'ltrb'
                if coords_mode == 'xywh':
                    # x1,y1: start; x2,y2: width,height 로 들어온다고 가정
                    start_x, start_y, width, height = x1, y1, x2, y2
                    if width < 0 or height < 0:
                        self.log.emit(f"경고: width/height가 음수입니다. 절대값으로 보정합니다 (w={width}, h={height})")
                        width, height = abs(width), abs(height)
                    if width == 0 or height == 0:
                        self.log.emit("경고: width/height가 0입니다. 크롭을 중지합니다.")
                        self.finished.emit("Crop 중지됨.")
                        return
                    x1, y1 = start_x, start_y
                    x2, y2 = start_x + width, start_y + height
            except Exception as e:
                self.log.emit(f"Crop 좌표 오류: {str(e)}")
                self.finished.emit("Crop 중지됨.")
                return

            # 2) 준비
            fov_numbers = None
            if fov_number_input:
                fov_numbers = self.parse_fov_numbers(fov_number_input)

            if not os.path.exists(source):
                self.log.emit(f"Source 경로 없음: {source}")
                self.finished.emit("Crop 중지됨.")
                return
            if not self.ensure_target_folder(target):
                self.finished.emit("Crop 중지됨.")
                return

            all_files = self.collect_crop_candidates(
                root_folder=source, formats=formats, fov_numbers=fov_numbers
            )
            total_images = len(all_files)
            if total_images == 0:
                self.log.emit("조건에 맞는 이미지 없음")
                self.finished.emit("Crop 완료.")
                return

            self.log.emit(f"총 Crop 대상 이미지 수: {total_images}")
            total_processed_images = 0
            crop_coords = (x1, y1, x2, y2)
            self.log.emit(f"Crop 영역(LTRB): {crop_coords}")

            # 3) 실행
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for (file_path, inner_id) in all_files:
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 처리 이미지 {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 처리 이미지: {total_processed_images}")
                        return

                    orig_filename = os.path.basename(file_path)
                    file_base, file_ext = os.path.splitext(orig_filename)

                    # 루트(=source) 바로 아래 있는 파일이면 원본 이름 그대로 유지
                    # 하위 폴더(폴더 기반 작업)에서 올라온 파일이면 inner_id 프리픽스 사용
                    use_prefix = (os.path.dirname(file_path) != source)
                    new_filename = f"{inner_id}_{orig_filename}" if use_prefix else orig_filename
                    dst_file = os.path.join(target, new_filename)

                    # BMP+JSON 페어 처리
                    src_dir = os.path.dirname(file_path)
                    json_path = os.path.join(src_dir, f"{file_base}.json")

                    if file_ext.lower() == ".bmp" and os.path.isfile(json_path):
                        new_base = os.path.splitext(new_filename)[0]
                        dst_json = os.path.join(target, f"{new_base}.json")
                        debug_draw_path = os.path.join(target, f"{new_base}_draw.bmp")
                        futures.append(
                            executor.submit(
                                self.crop_image_and_json_pair,
                                file_path, dst_file, json_path, dst_json, crop_coords, debug_draw_path
                            )
                        )
                    else:
                        futures.append(executor.submit(self.crop_image, file_path, dst_file, crop_coords))

                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 처리 이미지 {total_processed_images}")
                        self.finished.emit(f"작업 중지됨. 처리 이미지: {total_processed_images}")
                        return
                    result = future.result()
                    if result:
                        total_processed_images += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed_images / total_images) * 100)
                        self.progress.emit(min(progress_percent, 100))

            self.finished.emit(f"Crop 완료. 처리 이미지: {total_processed_images}")
            self.log.emit("------ Crop 작업 완료 ------")

        except Exception as e:
            logging.error("Crop 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Crop 중 오류 발생.")


    ########################################################################
    # A) Attach FOV
    ########################################################################
    def attach_fov(self, task):
        self.log.emit("------ Attach FOV 작업 시작 ------")
        try:
            search1 = task.get('search1', '')
            search2 = task.get('search2', '')
            target = task.get('target', '')
            fov_number_input = task.get('fov_number', '').strip()
            if not os.path.isdir(search1) or not os.path.isdir(search2):
                self.log.emit("Search Folder Path 오류")
                self.finished.emit("Attach FOV 중지됨.")
                return
            if not self.ensure_target_folder(target):
                self.finished.emit("Attach FOV 중지됨.")
                return
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
                fov_numbers = set(fov_numbers) if fov_numbers else None
            else:
                fov_numbers = None
            dict1 = self.recursive_find_fov_images(search1)
            dict2 = self.recursive_find_fov_images(search2)
            intersection_keys = set(dict1.keys()).intersection(set(dict2.keys()))
            if fov_numbers is not None:
                intersection_keys = {k for k in intersection_keys if k[1] in fov_numbers}
            if not intersection_keys:
                self.log.emit("교집합 fov 이미지 없음")
                self.finished.emit("Attach FOV 완료.")
                return
            total_jobs = 0
            for k in intersection_keys:
                total_jobs += min(len(dict1[k]), len(dict2[k]))
            self.log.emit(f"총 attach 건수: {total_jobs}")
            total_processed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for key in intersection_keys:
                    images_list_1 = dict1[key]
                    images_list_2 = dict2[key]
                    pair_count = min(len(images_list_1), len(images_list_2))
                    for i in range(pair_count):
                        src_file_1 = images_list_1[i]
                        src_file_2 = images_list_2[i]
                        futures.append(executor.submit(self.attach_two_images, src_file_1, src_file_2, key, target))
                for future in as_completed(futures):
                    if self._is_stopped:
                        self.log.emit(f"작업 중지: 처리 이미지 쌍 {total_processed}")
                        self.finished.emit(f"Attach FOV 중지됨. 처리 이미지 쌍: {total_processed}")
                        return
                    result = future.result()
                    if result.startswith("오류 발생"):
                        self.log.emit(result)
                    else:
                        total_processed += 1
                        self.log.emit(result)
                        progress_percent = int((total_processed / total_jobs) * 100)
                        self.progress.emit(min(progress_percent, 100))
            self.finished.emit(f"Attach FOV 완료. 처리 이미지 쌍: {total_processed}")
            self.log.emit("------ Attach FOV 작업 완료 ------")
        except Exception as e:
            logging.error("Attach FOV 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("Attach FOV 중 오류 발생.")

    def recursive_find_fov_images(self, root_folder):
        ignore_list = {'ok', 'ng', 'ng_info', 'crop', 'thumbnail'}
        result_dict = {}
        for dirpath, dirnames, filenames in os.walk(root_folder):
            dirnames[:] = [d for d in dirnames if d.lower() not in ignore_list]
            folder_name = os.path.basename(dirpath)
            if folder_name.lower() in ignore_list:
                continue
            last15 = folder_name[-15:] if len(folder_name) >= 15 else folder_name
            for filename in filenames:
                if filename.lower().startswith('fov') and filename.lower().endswith('.jpg'):
                    fovnum = ''.join(filter(str.isdigit, filename.lower().replace('fov', '')))
                    if not fovnum:
                        continue
                    key = (last15, fovnum)
                    full_path = os.path.join(dirpath, filename)
                    if key not in result_dict:
                        result_dict[key] = []
                    result_dict[key].append(full_path)
        return result_dict

    def attach_two_images(self, src1, src2, key, target):
        try:
            if self._is_stopped:
                return "오류 발생: 사용자 중지 요청"
            last15, fovnum = key
            im1 = Image.open(src1)
            im2 = Image.open(src2)
            width = im1.width + im2.width
            height = max(im1.height, im2.height)
            new_img = Image.new('RGB', (width, height), (255, 255, 255))
            new_img.paste(im1, (0, 0))
            new_img.paste(im2, (im1.width, 0))
            draw = ImageDraw.Draw(new_img)
            font = ImageFont.load_default()
            draw.text((10, 10), f"{os.path.basename(src1)}\nfov:{fovnum}", fill=(0, 0, 0), font=font)
            draw.text((im1.width + 10, 10), f"{os.path.basename(src2)}\nfov:{fovnum}", fill=(0, 0, 0), font=font)
            out_filename = f"attached_{last15}_{fovnum}.jpg"
            dst_file = os.path.join(target, out_filename)
            new_img.save(dst_file)
            return f"Attached: {src1} + {src2} => {dst_file}"
        except Exception as e:
            logging.error("attach_two_images 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    def mim_to_bmp(self, task):
        """
        ▸ task['ini_path'] 하나만 받아 해당 ini 로 mim2color.exe 실행
        ▸ 현재 작업 폴더(os.getcwd())에서 mim2color.exe 를 찾아 새 콘솔로 띄운다.
        """
        self.log.emit("------ MIM to BMP 작업 시작 ------")
        try:
            import sys, subprocess, os, logging

            # ────────────────────────────────────────────────────────────
            # 1) 실행 파일 위치 결정
            #    ‣ ① CWD 에 mim2color.exe 있음 → OK
            #    ‣ ② 없으면  스크립트(.py) 가 있는 폴더에서 재시도
            # ────────────────────────────────────────────────────────────
            cwd_dir   = os.getcwd()
            exe_path  = os.path.join(cwd_dir, 'mim2color.exe')

            if not os.path.isfile(exe_path):
                script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                exe_path   = os.path.join(script_dir, 'mim2color.exe')

            if not os.path.isfile(exe_path):
                self.log.emit(f"mim2color.exe 를 찾을 수 없습니다:\n  {cwd_dir}\n  {exe_path}")
                self.finished.emit("MIM to BMP 중지됨.")
                return

            ini_path = task.get('ini_path', '').strip()
            if not ini_path or not os.path.isfile(ini_path):
                self.log.emit("INI 경로가 유효하지 않습니다.")
                self.finished.emit("MIM to BMP 중지됨.")
                return

            self.log.emit(f"INI 사용: {ini_path}")
            self.log.emit(f"실행 파일: {exe_path}")

            # ─ 새 콘솔 창 플래그 (Windows) ────────────────────────────
            creation_flags = 0
            if os.name == 'nt':
                creation_flags = getattr(subprocess,
                                         'CREATE_NEW_CONSOLE', 0x00000010)

            # ─ 콘솔 창을 열고 실행 (stdout/stderr 는 새 콘솔로) ──────
            subprocess.Popen(
                [exe_path, ini_path],
                cwd=os.path.dirname(exe_path),      # exe 와 같은 폴더
                creationflags=creation_flags
            )

            self.progress.emit(100)
            self.finished.emit("mim2color.exe 실행 지시 완료 (새 콘솔 창).")
            self.log.emit("------ 작업 지시 후 종료 ------")

        except Exception as e:
            logging.error("MIM to BMP 오류", exc_info=True)
            self.log.emit(f"오류 발생: {e}")
            self.finished.emit("MIM to BMP 중 오류 발생.")

    ########################################################################
    # C) TEMP
    ########################################################################
    def btj_operation(self, task):
            """
            BTJ 기능: 
            - 입력 폴더(또는 여러 폴더)를 재귀 탐색하며 .bmp 파일을 모두 찾아 .jpg로 변환
            - output 경로가 없으면 input + '_JPG' 폴더를 자동 생성
            """
            self.log.emit("------ BMP TO JPG 작업: BMP -> JPG 변환 시작 ------")
            try:
                source = task.get('source', '').strip()
                target = task.get('target', '').strip()

                # 만약 target이 비었다면, source + '_JPG' 로 자동 생성
                if not target:
                    # source가 폴더인지 확인
                    # - 만약 source가 'C:/images' 이라면 'C:/images_JPG' 로 세팅
                    target = f"{source}_JPG"

                # Target 폴더 생성 시도
                if not self.ensure_target_folder(target):
                    self.finished.emit("BMP->JPG 변환 중지됨 (Target 생성 실패).")
                    return

                # Source 존재 여부 체크
                if not os.path.isdir(source):
                    self.log.emit(f"Source 경로가 유효하지 않습니다: {source}")
                    self.finished.emit("BMP->JPG 변환 중지됨.")
                    return

                # 1) .bmp 파일 전체 목록 수집
                bmp_files = []
                for dirpath, dirnames, filenames in os.walk(source):
                    if self._is_stopped:
                        self.log.emit("사용자에 의해 중지됨.")
                        self.finished.emit("BMP->JPG 변환 중지됨.")
                        return
                    for filename in filenames:
                        if filename.lower().endswith('.bmp'):
                            full_path = os.path.join(dirpath, filename)
                            bmp_files.append(full_path)

                total_bmp = len(bmp_files)
                if total_bmp == 0:
                    self.log.emit("변환할 .bmp 파일이 없습니다.")
                    self.finished.emit("BMP->JPG 변환 완료 (처리 대상 0).")
                    return

                self.log.emit(f"총 변환 대상 BMP 파일: {total_bmp}개")
                self.log.emit(f"Target 폴더: {target}")

                # 2) ThreadPoolExecutor로 변환 진행
                converted_count = 0
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    for bmp_path in bmp_files:
                        if self._is_stopped:
                            break
                        # 변환 후 저장될 jpg 경로를 결정
                        # - source 내 하위 경로 구조를 target 내에 그대로 반영하려면:
                        #   dirpath - source를 기준으로 상대경로를 구해서 target에 합침
                        rel_path = os.path.relpath(bmp_path, source)  # source 기준 상대경로
                        # 확장자만 .jpg 로 바꾸기
                        rel_no_ext = os.path.splitext(rel_path)[0]  # 확장자 제거
                        out_path = os.path.join(target, rel_no_ext + '.jpg')

                        # 혹시 상위 디렉토리가 없다면 생성
                        out_dir = os.path.dirname(out_path)
                        if not os.path.exists(out_dir):
                            os.makedirs(out_dir, exist_ok=True)

                        futures.append(executor.submit(self.convert_bmp_to_jpg, bmp_path, out_path))

                    for future in as_completed(futures):
                        if self._is_stopped:
                            self.log.emit(f"사용자 중지 요청으로 작업 중단. 현재까지 {converted_count}개 변환 완료.")
                            self.finished.emit("BMP->JPG 변환 중단됨.")
                            return
                        result = future.result()
                        if result.startswith("오류 발생"):
                            self.log.emit(result)
                        else:
                            converted_count += 1
                            self.log.emit(result)
                            # 진행률 표시
                            progress_percent = int((converted_count / total_bmp) * 100)
                            self.progress.emit(min(progress_percent, 100))

                self.log.emit("BMP->JPG 변환 작업 완료")
                self.finished.emit(f"BMP->JPG 변환 완료 (총 {converted_count}개).")
            except Exception as e:
                logging.error("BTJ(BMP->JPG 변환) 중 오류", exc_info=True)
                self.log.emit(f"오류 발생: {str(e)}")
                self.finished.emit("BMP->JPG 변환 중 오류 발생.")

    def convert_bmp_to_jpg(self, src, dst):
        """
        실제 bmp 이미지를 jpg로 변환하는 함수
        """
        if self._is_stopped:
            return "오류 발생: 사용자 중지 요청"
        try:
            with Image.open(src) as img:
                # PIL 이미지의 모드가 "RGBA" 등일 수 있으므로, 필요한 경우 RGB 변환
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                elif img.mode == "RGBA":
                    # 알파 채널이 있을 경우 배경 흰색으로 합성
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])  # 3은 alpha channel
                    img = background

                img.save(dst, "JPEG")
            return f"Converted BMP -> JPG: {src} -> {dst}"
        except Exception as e:
            logging.error(f"BMP->JPG 변환 오류 ({src})", exc_info=True)
            # 필요하다면 dst가 이미 생겼으면 제거
            if os.path.exists(dst):
                os.remove(dst)
            return f"오류 발생: {str(e)}"

    ########################################################################
    # 유틸 함수들
    ########################################################################
    def is_valid_file(self, filename, formats):
        if not formats:
            return False
        fname_lower = filename.lower()
        base, ext = os.path.splitext(fname_lower)
        for fmt in formats:
            fmt_lower = fmt.lower()
            if fmt_lower == 'org_jpg':
                if ext == '.jpg' and 'fov' not in base:
                    return True
            elif fmt_lower == 'fov_jpg':
                if ext == '.jpg' and 'fov' in base:
                    return True
            else:
                if fname_lower.endswith(fmt_lower):
                    return True
        return False

    def copy_file_chunked(self, src, dst):
        if self._is_stopped:
            return "오류 발생: 사용자 중지 요청"
        try:
            with open(src, 'rb') as sf, open(dst, 'wb') as df:
                while True:
                    if self._is_stopped:
                        df.close()
                        if os.path.exists(dst):
                            os.remove(dst)
                        return "오류 발생: 사용자 중지 요청"
                    data = sf.read(1024 * 1024)
                    if not data:
                        break
                    df.write(data)
            return f"Copied {src} to {dst}"
        except Exception as e:
            logging.error("파일 복사 오류", exc_info=True)
            if os.path.exists(dst):
                os.remove(dst)
            return f"오류 발생: {str(e)}"

    def copy_folder(self, src, dst):
        if self._is_stopped:
            return "오류 발생: 사용자 중지 요청"
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True)
            return f"Copied folder {src} to {dst}"
        except Exception as e:
            logging.error("폴더 복사 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

    def copy_folder_filtered(self, src, dst, formats):
        if self._is_stopped:
            return "오류 발생: 사용자 중지 요청"
        try:
            if not os.path.exists(dst):
                os.makedirs(dst)
            count = 0
            with os.scandir(src) as it:
                for entry in it:
                    if self._is_stopped:
                        return "오류 발생: 사용자 중지 요청"
                    if entry.is_file() and self.is_valid_file(entry.name, formats):
                        src_file = os.path.join(src, entry.name)
                        dst_file = os.path.join(dst, entry.name)
                        result = self.copy_file_chunked(src_file, dst_file)
                        if not result.startswith("오류 발생"):
                            count += 1
            return f"Copied {count} file(s) from {src} to {dst} (filtered)"
        except Exception as e:
            logging.error("Filtered folder copy 오류", exc_info=True)
            return f"오류 발생: {str(e)}"

## ============================
    def crop_image_and_json_pair(self, src_img, dst_img, src_json, dst_json, crop_coords, debug_draw_path):
        """
        BMP를 크롭 저장하고, 동명이본 JSON을 같은 크롭 오프셋만큼 보정하여 저장.
        디버그용으로 라벨/박스를 그린 _draw 이미지를 추가 저장.
        """
        try:
            # 1) 이미지 크롭
            with Image.open(src_img) as img:
                img = ImageOps.exif_transpose(img)
                img.load()

                x1, y1, x2, y2 = crop_coords
                # 정규화/클램프 (기존 crop_image와 동일 규칙)
                if x1 > x2: x1, x2 = x2, x1
                if y1 > y2: y1, y2 = y2, y1
                w, h = img.size
                x1 = max(0, min(x1, w))
                y1 = max(0, min(y1, h))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                if x2 <= x1 or y2 <= y1:
                    return f"SKIP: 크롭 영역이 유효하지 않음 (img={w}x{h}, box=({x1},{y1},{x2},{y2}))"

                cropped = img.crop((x1, y1, x2, y2))
                try:
                    cropped.save(dst_img)
                except OSError:
                    cropped = cropped.convert("RGB")
                    cropped.save(dst_img)

                new_w, new_h = cropped.size

            # 2) JSON 보정 & 저장
            self._adjust_and_save_json(
                src_json_path=src_json,
                dst_json_path=dst_json,
                crop_box=(x1, y1, x2, y2),
                new_size=(new_w, new_h),
                new_image_filename=os.path.basename(dst_img),
                debug_draw_path=debug_draw_path,   # 디버그 드로잉도 여기서 처리
                debug_base_image_path=dst_img
            )

            return f"Cropped+JSON {src_img} -> {dst_img}, JSON -> {dst_json}"

        except Exception as e:
            logging.error("crop_image_and_json_pair 오류", exc_info=True)
            # 실패 시 생성물 정리(부분 파일 삭제)
            try:
                if os.path.exists(dst_img): os.remove(dst_img)
                if os.path.exists(dst_json): os.remove(dst_json)
                if os.path.exists(debug_draw_path): os.remove(debug_draw_path)
            except:
                pass
            return f"오류 발생: {str(e)}"


    def _adjust_and_save_json(self, src_json_path, dst_json_path, crop_box, new_size, new_image_filename,
                            debug_draw_path=None, debug_base_image_path=None):
        """
        Labelme 유사 JSON을 크롭 오프셋만큼 보정하여 저장.
        - shapes[*].points: (x-x1, y-y1) 보정 + 경계 클램프
        - bbox: points로 재계산하여 반영
        - rois: [x1,y1,x2,y2] 보정 + 경계 클램프
        - imagePath, imageWidth, imageHeight 갱신
        - debug_draw_path가 주어지면, 크롭된 이미지를 불러 라벨/박스를 그려 저장
        """
        with open(src_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        x1, y1, x2, y2 = crop_box
        new_w, new_h = new_size

        shapes = data.get("shapes", [])
        for shp in shapes:
            pts = shp.get("points", [])
            shape_type = (shp.get("shape_type") or "").lower()
            adj_pts = []
            for p in pts:
                if not isinstance(p, (list, tuple)) or len(p) < 2:
                    continue
                px, py = p[0], p[1]
                nx = max(0.0, min(float(px) - float(x1), float(new_w)))
                ny = max(0.0, min(float(py) - float(y1), float(new_h)))
                adj_pts.append([nx, ny])

            if adj_pts:
                shp["points"] = adj_pts

            bbox = shp.get("bbox") if isinstance(shp.get("bbox"), dict) else None

            if shape_type == "point":
                # point는 좌표만 평행이동하고, bbox의 width/height는 원래 값을 보존
                if bbox is not None:
                    old_x = float(bbox.get("x", adj_pts[0][0]))
                    old_y = float(bbox.get("y", adj_pts[0][1]))
                    old_w = float(bbox.get("width", 0) or 0.0)
                    old_h = float(bbox.get("height", 0) or 0.0)

                    # bbox의 좌상단(x,y)을 크롭 오프셋만큼 이동 + 경계 클램프
                    nx = max(0.0, min(old_x - float(x1), float(new_w)))
                    ny = max(0.0, min(old_y - float(y1), float(new_h)))

                    # 크기 유지(원래 0이면 그대로 0, 이미지 경계를 넘으면 내부로 클램프)
                    if old_w > 0 and old_h > 0:
                        nx2 = min(nx + old_w, float(new_w))
                        ny2 = min(ny + old_h, float(new_h))
                        old_w = max(0.0, nx2 - nx)
                        old_h = max(0.0, ny2 - ny)

                    bbox["x"] = nx
                    bbox["y"] = ny
                    bbox["width"] = old_w
                    bbox["height"] = old_h
                    shp["bbox"] = bbox
                # point는 여기서 처리 종료(아래의 공통 bbox 재계산 로직 타면 안 됨)

            elif bbox and float(bbox.get("width", 0)) == 0.0 and float(bbox.get("height", 0)) == 0.0 and len(adj_pts) == 1:
                # 폭/높이가 0인 point 유사 도형: 위치만 이동, 0x0 유지
                bbox["x"] = float(adj_pts[0][0])
                bbox["y"] = float(adj_pts[0][1])
                bbox["width"] = 0.0
                bbox["height"] = 0.0

            else:
                # 일반 도형: points로 bbox 재계산
                xs = [p[0] for p in adj_pts]
                ys = [p[1] for p in adj_pts]
                minx, maxx = max(0.0, min(xs)), min(float(new_w), max(xs))
                miny, maxy = max(0.0, min(ys)), min(float(new_h), max(ys))
                width = max(0.0, maxx - minx)
                height = max(0.0, maxy - miny)
                if bbox is not None:
                    bbox["x"] = float(minx)
                    bbox["y"] = float(miny)
                    bbox["width"] = float(width)
                    bbox["height"] = float(height)


        # 2) rois 보정 (리스트 안에 [x1,y1,x2,y2] 형태로 있다고 가정)
        rois = data.get("rois", None)
        if isinstance(rois, list):
            new_rois = []
            for item in rois:
                if isinstance(item, (list, tuple)) and len(item) >= 4:
                    rx1 = max(0, min(int(item[0]) - int(x1), new_w))
                    ry1 = max(0, min(int(item[1]) - int(y1), new_h))
                    rx2 = max(0, min(int(item[2]) - int(x1), new_w))
                    ry2 = max(0, min(int(item[3]) - int(y1), new_h))
                    # 좌표 역전 방지
                    if rx2 < rx1: rx1, rx2 = rx2, rx1
                    if ry2 < ry1: ry1, ry2 = ry2, ry1
                    new_rois.append([rx1, ry1, rx2, ry2])
                else:
                    new_rois.append(item)  # 형식이 다르면 그대로 보존
            data["rois"] = new_rois

        # 3) 이미지 메타 갱신
        data["imagePath"] = new_image_filename
        data["imageWidth"] = int(new_w)
        data["imageHeight"] = int(new_h)

        # 저장
        with open(dst_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        # 4) 디버그 드로잉
        if debug_draw_path and debug_base_image_path:
            try:
                self._draw_debug_labels(debug_base_image_path, data, debug_draw_path)
            except Exception as e:
                logging.error("디버그 드로잉 오류", exc_info=True)


    def _draw_debug_labels(self, image_path, data, save_path):
        with Image.open(image_path) as im:
            draw = ImageDraw.Draw(im)

            for shp in data.get("shapes", []):
                pts = shp.get("points", [])
                shape_type = (shp.get("shape_type") or "").lower()

                # 점
                if shape_type == "point" and isinstance(pts, list) and len(pts) == 1:
                    cx, cy = float(pts[0][0]), float(pts[0][1])
                    r = 4  # 표시 반지름(디버그용)
                    try:
                        draw.ellipse([cx - r, cy - r, cx + r, cy + r], width=2)
                    except:
                        pass
                # 폴리곤/선 등
                elif isinstance(pts, list) and len(pts) >= 2:
                    try:
                        draw.line([tuple(p) for p in pts] + [tuple(pts[0])], width=2)
                    except:
                        pass

                # bbox
                bbox = shp.get("bbox")
                if isinstance(bbox, dict):
                    x = float(bbox.get("x", 0))
                    y = float(bbox.get("y", 0))
                    w = float(bbox.get("width", 0))
                    h = float(bbox.get("height", 0))
                    x2, y2 = x + w, y + h
                    try:
                        # 점 bbox(0,0)는 작게 표시(선택)
                        if w == 0.0 and h == 0.0:
                            rr = 5
                            draw.ellipse([x - rr, y - rr, x + rr, y + rr], width=1)
                        else:
                            draw.rectangle([x, y, x2, y2], width=2)
                    except:
                        pass

            try:
                im.save(save_path)
            except OSError:
                im.convert("RGB").save(save_path)




    def crop_image(self, src, dst, crop_coords):
        if self._is_stopped:
            return "오류 발생: 사용자 중지 요청"
        try:
            with Image.open(src) as img:
                # 1) EXIF 회전 보정 + 실제 로드
                img = ImageOps.exif_transpose(img)
                img.load()

                w, h = img.size
                x1, y1, x2, y2 = crop_coords

                # 2) 좌표 정규화(뒤집힘 방지)
                if x1 > x2: x1, x2 = x2, x1
                if y1 > y2: y1, y2 = y2, y1

                # 3) 경계 클램핑(이미지 밖 방지)
                x1 = max(0, min(x1, w))
                y1 = max(0, min(y1, h))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))

                # 4) 유효성 검사
                if x2 <= x1 or y2 <= y1:
                    return f"SKIP: 크롭 영역이 유효하지 않음 (img={w}x{h}, box={crop_coords})"

                cropped = img.crop((x1, y1, x2, y2))

                try:
                    cropped.save(dst)
                except OSError:
                    cropped = cropped.convert("RGB")
                    cropped.save(dst)

                return f"Cropped {src} -> {dst} (img={w}x{h}, box=({x1},{y1},{x2},{y2}))"

        except Exception as e:
            logging.error(f"이미지 크롭 오류: {src}", exc_info=True)
            return f"오류 발생: {str(e)}"

    def parse_fov_numbers(self, fov_str):
        results = set()
        parts = [p.strip() for p in fov_str.split(',') if p.strip()]
        for part in parts:
            if '/' in part:
                try:
                    start, end = part.split('/')
                    start_i = int(start.strip())
                    end_i = int(end.strip())
                    if start_i <= end_i:
                        for n in range(start_i, end_i+1):
                            results.add(str(n))
                except:
                    pass
            else:
                if part.isdigit():
                    results.add(part)
        return results if results else None

    def collect_crop_candidates(self, root_folder, formats, fov_numbers=None):
        ignore_list = {'ok','ng','ng_info','crop','thumbnail'}
        collected_files = []
        for dirpath, dirnames, filenames in os.walk(root_folder):
            dirnames[:] = [d for d in dirnames if d.lower() not in ignore_list]
            folder_name = os.path.basename(dirpath)
            if folder_name.lower() in ignore_list:
                continue
            rel_path = os.path.relpath(dirpath, root_folder)
            parts = rel_path.split(os.sep)
            candidate_inner_id = parts[0] if parts else folder_name
            for filename in filenames:
                if self.is_valid_file(filename, formats):
                    if fov_numbers:
                        prefix = filename.split('_', 1)[0].lower()
                        digits = re.sub(r'[^0-9]', '', prefix)
                        if digits not in fov_numbers:
                            continue
                    full_path = os.path.join(dirpath, filename)
                    collected_files.append((full_path, candidate_inner_id))
        return collected_files

    def collect_inner_ids(self, sources):
        inner_ids = set()
        if isinstance(sources, list):
            for source in sources:
                if not os.path.exists(source):
                    self.log.emit(f"Source 경로 없음: {source}")
                    continue
                folder_name = os.path.basename(source.rstrip(os.sep))
                if folder_name.lower() not in ['ok','ng','ng_info','crop','thumbnail']:
                    inner_ids.add(folder_name)
        else:
            if not os.path.exists(sources):
                self.log.emit(f"Source 경로 없음: {sources}")
            else:
                folder_name = os.path.basename(sources.rstrip(os.sep))
                if folder_name.lower() not in ['ok','ng','ng_info','crop','thumbnail']:
                    inner_ids.add(folder_name)
        return inner_ids

    def collect_inner_ids_from_source2(self, source2):
        inner_ids = set()
        if not os.path.exists(source2):
            self.log.emit(f"Source2 경로 없음: {source2}")
            return inner_ids
        try:
            with os.scandir(source2) as it:
                inner_ids = {entry.name for entry in it if entry.is_dir() and entry.name.lower() not in ['ok','ng','ng_info','crop','thumbnail']}
        except Exception as e:
            self.log.emit(f"Source2에서 Inner ID 수집 오류: {str(e)}")
        return inner_ids

    def collect_images_to_copy(self, inner_ids, source, formats):
        images_to_copy = {}
        total_images = 0
        for inner_id in inner_ids:
            source_inner_id_folder = os.path.join(source, inner_id)
            if not os.path.exists(source_inner_id_folder):
                self.log.emit(f"Source 내 폴더 없음: {source_inner_id_folder}")
                continue
            try:
                with os.scandir(source_inner_id_folder) as it:
                    images = [entry.name for entry in it if entry.is_file() and self.is_valid_file(entry.name, formats)]
                if images:
                    images_to_copy[inner_id] = images
                    total_images += len(images)
            except Exception as e:
                self.log.emit(f"이미지 수집 오류: {source_inner_id_folder} | 에러: {e}")
        return images_to_copy, total_images